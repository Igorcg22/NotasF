import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Carrega variáveis do arquivo .env
load_dotenv()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Configurações do Banco de Dados
DB_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost/projeto_financeiro")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELOS (Regras de Negócio UniRV) ---
class Fornecedor(Base):
    __tablename__ = "fornecedores"
    id = Column(Integer, primary_key=True); razao_social = Column(String(255))
    cnpj = Column(String(20), unique=True); status = Column(String(10), default="ATIVO")

class Faturado(Base):
    __tablename__ = "faturados"
    id = Column(Integer, primary_key=True); nome = Column(String(255))
    cpf = Column(String(20), unique=True); status = Column(String(10), default="ATIVO")

class Classificacao(Base):
    __tablename__ = "classificacao"
    id = Column(Integer, primary_key=True); descricao = Column(String(100), unique=True)

class Movimento(Base):
    __tablename__ = "movimentocontas"
    id = Column(Integer, primary_key=True); numero_nota = Column(String(50))
    valor_total = Column(Float); data_emissao = Column(Date)
    id_fornecedor = Column(Integer, ForeignKey("fornecedores.id"))
    id_faturado = Column(Integer, ForeignKey("faturados.id"))

class MovimentoClass(Base):
    __tablename__ = "movimento_classificacao"
    id_movimento = Column(Integer, ForeignKey("movimentocontas.id"), primary_key=True)
    id_classificacao = Column(Integer, ForeignKey("classificacao.id"), primary_key=True)

class Parcela(Base):
    __tablename__ = "parcelacontas"
    id = Column(Integer, primary_key=True); id_movimento = Column(Integer, ForeignKey("movimentocontas.id"))
    vencimento = Column(Date); valor = Column(Float)

Base.metadata.create_all(bind=engine)

# --- CONFIGURAÇÃO IA ---
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

def formatar_data(d, data_emissao=None):
    try:
        if not d: return data_emissao
        limpa = re.sub(r'[^\d/-]', '', str(d))
        if "/" in limpa: return datetime.strptime(limpa, "%d/%m/%Y").date()
        return datetime.strptime(limpa[:10], "%Y-%m-%d").date()
    except: return data_emissao

@app.post("/processar-nota")
async def processar(file: UploadFile = File(...)):
    db = SessionLocal()
    try:
        content = await file.read()
        model = genai.GenerativeModel('gemini-flash-latest')
        prompt = """Extraia JSON: {numero_nota, data_emissao, valor_total, 
        fornecedor:{razao_social, cnpj}, faturado:{nome, cpf}, 
        parcelas:[{vencimento, valor}], categorias:[string]}"""
        
        response = model.generate_content([prompt, {"mime_type": "application/pdf", "data": content}])
        ext = json.loads(re.search(r'\{.*\}', response.text, re.DOTALL).group(0))

        # Analisa se já existem no banco
        f = db.query(Fornecedor).filter(Fornecedor.cnpj == ext['fornecedor']['cnpj']).first()
        fat = db.query(Faturado).filter(Faturado.cpf == ext['faturado']['cpf']).first()
        
        return {
            "extracao": ext,
            "analise": {
                "fornecedor": {"status": f.status if f else "NÃO EXISTE", "id": f.id if f else None},
                "faturado": {"status": fat.status if fat else "NÃO EXISTE", "id": fat.id if fat else None}
            }
        }
    finally: db.close()

@app.post("/lancar")
async def lancar(req: dict):
    db = SessionLocal()
    try:
        ext = req['extracao']; anl = req['analise']
        
        # 1. Tratar Fornecedor (Regra: Reativar se estiver Inativo)
        f_id = anl['fornecedor']['id']
        if not f_id:
            forn = Fornecedor(razao_social=ext['fornecedor']['razao_social'], cnpj=ext['fornecedor']['cnpj'])
            db.add(forn); db.flush(); f_id = forn.id
        else:
            forn = db.query(Fornecedor).get(f_id)
            if forn.status == "INATIVO": forn.status = "ATIVO"

        # 2. Tratar Faturado (Regra: Reativar se estiver Inativo)
        fat_id = anl['faturado']['id']
        if not fat_id:
            fat = Faturado(nome=ext['faturado']['nome'], cpf=ext['faturado']['cpf'])
            db.add(fat); db.flush(); fat_id = fat.id
        else:
            fat = db.query(Faturado).get(fat_id)
            if fat.status == "INATIVO": fat.status = "ATIVO"

        # 3. Criar Movimento
        data_emi = formatar_data(ext['data_emissao'])
        mov = Movimento(numero_nota=ext['numero_nota'], valor_total=float(ext['valor_total']), data_emissao=data_emi, id_fornecedor=f_id, id_faturado=fat_id)
        db.add(mov); db.flush()

        # 4. Gravar Múltiplas Categorias
        if 'categorias' in ext:
            for cat_nome in ext['categorias']:
                c = db.query(Classificacao).filter(Classificacao.descricao.like(f"%{cat_nome}%")).first()
                if c: db.add(MovimentoClass(id_movimento=mov.id, id_classificacao=c.id))
        
        # 5. Gravar Múltiplas Parcelas (Regra: Data emissão se vazio)
        if 'parcelas' in ext and len(ext['parcelas']) > 0:
            for p in ext['parcelas']:
                venc = formatar_data(p.get('vencimento'), data_emissao=data_emi)
                db.add(Parcela(id_movimento=mov.id, vencimento=venc, valor=float(p.get('valor', ext['valor_total']))))
        else:
            db.add(Parcela(id_movimento=mov.id, vencimento=data_emi, valor=float(ext['valor_total'])))

        db.commit()
        return {"message": "Lançamento efetuado com sucesso!"}
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=500, detail=str(e))
    finally: db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)