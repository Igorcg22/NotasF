DROP DATABASE IF EXISTS projeto_financeiro;
CREATE DATABASE projeto_financeiro;
USE projeto_financeiro;

CREATE TABLE pessoas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    razao_social VARCHAR(255) NOT NULL,
    documento VARCHAR(20) NOT NULL UNIQUE,
    tipo VARCHAR(50), -- FORNECEDOR ou FATURADO
    status VARCHAR(10) DEFAULT 'ATIVO' -- Regra: Cadastros devem ser INATIVADOS
);

CREATE TABLE classificacao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    descricao VARCHAR(100) NOT NULL UNIQUE,
    tipo VARCHAR(20) -- RECEITA ou DESPESA
);

CREATE TABLE movimentocontas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero_nota VARCHAR(50),
    valor_total DECIMAL(10,2),
    data_emissao DATE,
    tipo_movimento ENUM('APAGAR', 'ARECEBER') DEFAULT 'APAGAR',
    id_fornecedor INT,
    id_faturado INT,
    FOREIGN KEY (id_fornecedor) REFERENCES pessoas(id),
    FOREIGN KEY (id_faturado) REFERENCES pessoas(id)
);

-- Regra: Um registro pode ter uma ou mais Tipo de DESPESAS/RECEITAS
CREATE TABLE movimento_classificacao (
    id_movimento INT,
    id_classificacao INT,
    PRIMARY KEY (id_movimento, id_classificacao),
    FOREIGN KEY (id_movimento) REFERENCES movimentocontas(id),
    FOREIGN KEY (id_classificacao) REFERENCES classificacao(id)
);

-- Regra: Um registro pode ter uma ou mais PARCELAS
CREATE TABLE parcelacontas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_movimento INT,
    vencimento DATE,
    valor DECIMAL(10,2),
    FOREIGN KEY (id_movimento) REFERENCES movimentocontas(id)
);

-- Inserir categorias padrão
INSERT INTO classificacao (descricao, tipo) VALUES 
('INSUMOS AGRÍCOLAS', 'DESPESA'), ('MANUTENÇÃO E OPERAÇÃO', 'DESPESA'),
('RECURSOS HUMANOS', 'DESPESA'), ('SERVIÇOS OPERACIONAIS', 'DESPESA'),
('INFRAESTRUTURA E UTILIDADES', 'DESPESA'), ('ADMINISTRATIVAS', 'DESPESA');

--view
CREATE OR REPLACE VIEW v_relatorio_financeiro_completo AS
SELECT 
    m.id AS id_movimento,
    m.numero_nota AS nota_fiscal,
    m.data_emissao AS data_emissao,
    f.razao_social AS fornecedor,
    fat.nome AS faturado_para,
    (SELECT GROUP_CONCAT(c.descricao SEPARATOR ', ') 
     FROM movimento_classificacao mc 
     JOIN classificacao c ON mc.id_classificacao = c.id 
     WHERE mc.id_movimento = m.id) AS categorias,
    p.vencimento AS data_vencimento,
    p.valor AS valor_parcela,
    m.valor_total AS valor_total_nota
FROM movimentocontas m
LEFT JOIN fornecedores f ON m.id_fornecedor = f.id
LEFT JOIN faturados fat ON m.id_faturado = fat.id
LEFT JOIN parcelacontas p ON m.id = p.id_movimento;