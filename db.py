import sqlite3

DATABASE='estoque.db'
LIMIAR_ESTOQUE_BAIXO = 10

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with open('schema.sql', 'r', encoding='utf8') as f:
        conn.executescript(f.read())
        conn.commit()
        conn.close()
        print('BANCO DE DADOS INICIALIZADO!')

#----------------------
# PRODUTOS
#----------------------
def criar_produto(nome, sku, descricao, preco, quantidade, localizacao):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # O INSERT agora está na mesma ordem dos VALUES
    cursor.execute(
        '''INSERT INTO produtos (nome, sku, descricao, preco, quantidade, localizacao) 
        VALUES(?, ?, ?, ?, ?, ?)''',
        (nome, sku, descricao, preco, quantidade, localizacao)
    )
    
    conn.commit()
    conn.close()

def atualizar_produto(produto_id, nome, sku, descricao, preco, quantidade, localizacao):
    """Atualiza todos os campos editáveis de um produto existente."""
    conn = get_db_connection()
    conn.execute(
        '''UPDATE produtos
           SET nome = ?, sku = ?, descricao = ?, preco = ?,
               quantidade = ?, localizacao = ?
           WHERE id = ?''',
        (nome, sku, descricao, preco, quantidade, localizacao, produto_id)
    )
    conn.commit()
    conn.close()

def get_todos_produtos(busca=None, pagina=1, por_pagina=10):
    """
    Lista produtos com suporte a pesquisa e paginação.

    Paginação funciona com LIMIT (quantos itens) e OFFSET (a partir de qual).
    Ex.: página 2, 10 por página → LIMIT 10 OFFSET 10.

    :param busca:     String de filtro (nome ou SKU); None = sem filtro
    :param pagina:    Número da página atual (começa em 1)
    :param por_pagina: Itens por página
    :return: Tupla (lista_de_produtos, total_de_registros)
    """
    conn = get_db_connection()
    offset = (pagina - 1) * por_pagina

    if busca:
        # O % no LIKE é o curinga do SQL: 'cam%' → começa com "cam"
        # '%cam%' → contém "cam" em qualquer posição
        filtro = f'%{busca}%'
        produtos = conn.execute(
            '''SELECT * FROM produtos
               WHERE nome LIKE ? OR sku LIKE ?
               ORDER BY nome ASC
               LIMIT ? OFFSET ?''',
            (filtro, filtro, por_pagina, offset)
        ).fetchall()
        total = conn.execute(
            'SELECT COUNT(*) FROM produtos WHERE nome LIKE ? OR sku LIKE ?',
            (filtro, filtro)
        ).fetchone()[0]
    else:
        produtos = conn.execute(
            'SELECT * FROM produtos ORDER BY nome ASC LIMIT ? OFFSET ?',
            (por_pagina, offset)
        ).fetchall()
        total = conn.execute(
            'SELECT COUNT(*) FROM produtos'
        ).fetchone()[0]

    conn.close()
    return produtos, total

def get_produto_id(produto_id):
    """Busca e retorna um único produto pelo seu ID."""
    conn = get_db_connection()  # <--- A variável conn é criada aqui!
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM produtos WHERE id = ?', (produto_id,))
    produto = cursor.fetchone()
    
    conn.close()
    
    # Retorna como dicionário para o HTML conseguir ler os campos
    return dict(produto) if produto else None

def get_produto_por_sku(sku, excluir_id=None):
    """
    Verifica se um SKU já existe no banco de dados.
    excluir_id é usado na edição: ignoramos o próprio produto
    ao checar duplicata de SKU.

    :return: Produto encontrado ou None
    id: 1
    sku: ABC-123
    Editando produto 1
    SKU: ABC-123
    CONFIRMAR> BUSCANDO TODOS OS PRODUTOS COM > SKU-123 E ONDE O id NAO SEJA 1
    
    """
    conn = get_db_connection()
    if excluir_id:
        produto = conn.execute(
            'SELECT id FROM produtos WHERE sku = ? AND id != ?',
            (sku, excluir_id)
        ).fetchone()
    else:
        produto = conn.execute(
            'SELECT id FROM produtos WHERE sku = ?', (sku,)
        ).fetchone()
    conn.close()
    return produto

def get_produtos_estoque_baixo():
    """
    Retorna todos os produtos abaixo do LIMIAR_ESTOQUE_BAIXO
    ordenasdos por menos aos mais criticos.
    """
    conn = get_db_connection()
    produtos = conn.execute(
            '''SELECT *FROM produtos
            WHERE quantidade < ?
            ORDER BY quantidade ASC''',
            (LIMIAR_ESTOQUE_BAIXO, )
    ).fetchall()
    conn.close()
    return produtos

def deletar_produto(produto_id):
    """Remove permanentemente um produto do banco de dados."""
    conn = get_db_connection()
    conn.execute('DELETE FROM produtos WHERE id = ?', (produto_id,))
    conn.commit()
    conn.close()

# --------------------------------------------------------------
# DASHBOARD
# --------------------------------------------------------------
def get_metricas_dashboard():
    """
    Retorna um dicionário com as métricas para o painel principal:
    - total_produtos   → quantidade de SKUs cadastrados
    - total_estoque_baixo → quantos estão abaixo do limiar
    - valor_total      → soma de (preço × quantidade) de todos os itens
    """
    conn = get_db_connection()

    total_produtos = conn.execute(
        'SELECT COUNT(*) FROM produtos'
    ).fetchone()[0]

    total_estoque_baixo = conn.execute(
        'SELECT COUNT(*) FROM produtos WHERE quantidade < ?',
        (LIMIAR_ESTOQUE_BAIXO,)
    ).fetchone()[0]

    # SUM pode retornar None se a tabela estiver vazia; usamos "or 0.0"
    valor_total = conn.execute(
        'SELECT SUM(preco * quantidade) FROM produtos'
    ).fetchone()[0] or 0.0    

    conn.close()

    return {
        'total_produtos': total_produtos,
        'total_estoque_baixo': total_estoque_baixo,
        'valor_total': valor_total,
    }

# --------------------------------------------------------------
# MOVIMENTAÇÕES DE ESTOQUE
# --------------------------------------------------------------

def registrar_transacao(produto_id, tipo, quantidade_transacao):
    """
    Registra uma movimentação rápida de estoque (entrada ou saída).
    Valida se há estoque suficiente antes de subtrair.

    :param tipo: 'entrada' (recebimento) ou 'saida' (venda/consumo)
    :param quantidade_transacao: Quantidade a movimentar (sempre positivo)
    :return: Tupla (sucesso: bool, mensagem: str)
    """
    conn = get_db_connection()

    produto = conn.execute(
        'SELECT quantidade, nome FROM produtos WHERE id = ?',
        (produto_id,)
    ).fetchone()

    if not produto:
        conn.close()
        return False, "Produto não encontrado."

    estoque_atual = produto['quantidade']

    if tipo == 'entrada':
        novo_estoque = estoque_atual + quantidade_transacao
        msg_tipo = "Entrada"
    elif tipo == 'saida':
        # Regra de negócio: não permitir estoque negativo
        if quantidade_transacao > estoque_atual:
            conn.close()
            return (
                False,
                f"Estoque insuficiente! Disponível: {estoque_atual} unidades."
            )
        novo_estoque = estoque_atual - quantidade_transacao
        msg_tipo = "Saída"
    else:
        conn.close()
        return False, "Tipo de transação inválido."

    conn.execute(
        'UPDATE produtos SET quantidade = ? WHERE id = ?',
        (novo_estoque, produto_id)
    )
    conn.commit()
    conn.close()

    return (
        True,
        f"{msg_tipo} de {quantidade_transacao} unidade(s) registrada. "
        f"Novo estoque: {novo_estoque} unidades."
    )


def get_produto_por_id(id):
    conn = sqlite3.connect('estoque.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM produtos WHERE id = ?", (id,))
    produto = cursor.fetchone()
    
    conn.close()
    
    # Retorna o produto como dicionário (ou None se não achar)
    return dict(produto) if produto else None

# ============================================================
# BUSCA DE DADOS
# ============================================================



def buscar_dados_relatorio():
    # Conecte ao seu banco (ajuste o nome do arquivo se necessário)
    conn = get_db_connection() # ou o nome que você usa
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()