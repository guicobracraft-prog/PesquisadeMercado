import sys
import os
import json
import csv
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), 'resources'))
from catalogo_api import CatalogoAPI

HISTORICO_DIR = "historico"
ULTIMO_SNAPSHOT = os.path.join(HISTORICO_DIR, "ultimo_snapshot.json")
ARQUIVO_VENDAS_ACUMULADAS = "vendas_acumuladas.csv"
FUSO_HORARIO = timezone(timedelta(hours=-3))  # Horário de Brasília

# ----------------------------------------------------------------------
# Funções auxiliares
# ----------------------------------------------------------------------

def carregar_ultimo_snapshot():
    if os.path.exists(ULTIMO_SNAPSHOT):
        with open(ULTIMO_SNAPSHOT, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def salvar_snapshot(produtos_com_estoque):
    os.makedirs(HISTORICO_DIR, exist_ok=True)
    agora_utc = datetime.now(timezone.utc)
    timestamp_utc = agora_utc.strftime("%Y%m%d_%H%M%S")
    arquivo = os.path.join(HISTORICO_DIR, f"snapshot_{timestamp_utc}.json")
    dados = {
        "timestamp": timestamp_utc,
        "timestamp_iso": agora_utc.isoformat(),
        "produtos": {
            str(p['id']): {
                "estoque": p.get('estoque', 0),
                "valor": p.get('valor', 0)
            } for p in produtos_com_estoque
        }
    }
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    with open(ULTIMO_SNAPSHOT, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return arquivo

def extrair_estoque_anterior(valor):
    if isinstance(valor, dict):
        return int(valor.get('estoque', 0))
    else:
        return int(valor)

def extrair_valor_anterior(valor):
    if isinstance(valor, dict):
        return float(valor.get('valor', 0))
    else:
        return 0.0

def formatar_moeda(valor):
    try:
        return f"R$ {float(valor):.2f}"
    except:
        return "R$ 0.00"

def gerar_relatorio_vendas(snapshot_anterior, produtos_atuais):
    vendas = []
    reposicoes = []
    sem_mudanca = 0

    dict_atual = {
        str(p['id']): {
            "estoque": p.get('estoque', 0),
            "valor": p.get('valor', 0),
            "categoria": p.get('categoria', '')
        } for p in produtos_atuais
    }
    dict_anterior = snapshot_anterior.get('produtos', {})

    todos_ids = set(dict_anterior.keys()) | set(dict_atual.keys())

    for pid in todos_ids:
        qtd_anterior = extrair_estoque_anterior(dict_anterior.get(pid, {"estoque": 0}))
        qtd_atual = int(dict_atual.get(pid, {"estoque": 0})["estoque"])
        valor_unit = float(dict_atual.get(pid, {"valor": 0})["valor"])
        diferenca = qtd_atual - qtd_anterior

        produto = next((p for p in produtos_atuais if str(p['id']) == pid), {})
        nome = produto.get('nome', produto.get('descricao', ''))
        categoria = produto.get('categoria', '')

        if diferenca < 0:
            vendas.append({
                'id': pid,
                'nome': nome,
                'categoria': categoria,
                'qtd_anterior': qtd_anterior,
                'qtd_atual': qtd_atual,
                'unidades': abs(diferenca),
                'valor_unit': valor_unit,
                'valor_total': abs(diferenca) * valor_unit
            })
        elif diferenca > 0:
            reposicoes.append({
                'id': pid,
                'nome': nome,
                'categoria': categoria,
                'qtd_anterior': qtd_anterior,
                'qtd_atual': qtd_atual,
                'unidades': diferenca,
                'valor_unit': valor_unit,
                'valor_total': diferenca * valor_unit
            })
        else:
            sem_mudanca += 1

    return vendas, reposicoes, sem_mudanca

def registrar_vendas_acumuladas(vendas, arquivo=ARQUIVO_VENDAS_ACUMULADAS):
    """
    Registra as vendas no arquivo acumulado, com colunas organizadas.
    """
    if not vendas:
        return

    agora_local = datetime.now(FUSO_HORARIO)
    timestamp_local = agora_local.strftime("%Y-%m-%d %H:%M:%S")
    arquivo_existe = os.path.exists(arquivo)

    if not arquivo_existe:
        with open(arquivo, 'w', encoding='utf-8') as f:
            f.write("DATA_HORA;ID;NOME;CATEGORIA;QUANTIDADE_VENDIDA;VALOR_UNITARIO;VALOR_TOTAL\n")

    with open(arquivo, 'a', encoding='utf-8') as f:
        for v in vendas:
            valor_unit = f"{v['valor_unit']:.2f}".replace('.', ',')
            valor_total = f"{v['valor_total']:.2f}".replace('.', ',')
            nome = v['nome'].replace(';', ' ')
            categoria = v.get('categoria', '').replace(';', ' ')
            f.write(f"{timestamp_local};{v['id']};{nome};{categoria};{v['unidades']};{valor_unit};{valor_total}\n")

    print(f"📁 Vendas acumuladas salvas em: {arquivo}")

def migrar_vendas_acumuladas(produtos=None):
    """
    Migra o arquivo de vendas acumuladas do formato antigo para o novo.
    """
    if not os.path.exists(ARQUIVO_VENDAS_ACUMULADAS):
        return

    with open(ARQUIVO_VENDAS_ACUMULADAS, 'r', encoding='utf-8') as f:
        linhas = f.readlines()

    if not linhas:
        return

    cabecalho = linhas[0].strip()
    colunas_antigas = cabecalho.split(';')
    colunas_novas = ["DATA_HORA", "ID", "NOME", "CATEGORIA", "QUANTIDADE_VENDIDA", "VALOR_UNITARIO", "VALOR_TOTAL"]

    # Se já estiver no formato novo, não faz nada
    if "CATEGORIA" in colunas_antigas and "VALOR_UNITARIO" in colunas_antigas:
        return

    dict_produtos = {}
    if produtos is not None:
        dict_produtos = {str(p['id']): p for p in produtos}
    else:
        try:
            api = CatalogoAPI()
            catalogo = api.buscar_catalogo_completo()
            produtos = api.extrair_produtos(catalogo)
            dict_produtos = {str(p['id']): p for p in produtos}
        except:
            pass

    idx_data = colunas_antigas.index("DATA_HORA") if "DATA_HORA" in colunas_antigas else 0
    idx_id = colunas_antigas.index("ID") if "ID" in colunas_antigas else 1
    idx_nome = colunas_antigas.index("NOME") if "NOME" in colunas_antigas else 2
    idx_qtd = colunas_antigas.index("QUANTIDADE_VENDIDA") if "QUANTIDADE_VENDIDA" in colunas_antigas else 3
    idx_valor_total = colunas_antigas.index("VALOR_TOTAL") if "VALOR_TOTAL" in colunas_antigas else 4

    novas_linhas = [";".join(colunas_novas) + "\n"]

    for linha in linhas[1:]:
        partes = linha.strip().split(';')
        if len(partes) < 5:
            continue

        data_hora = partes[idx_data]
        pid = partes[idx_id]
        nome = partes[idx_nome]
        qtd = partes[idx_qtd]
        valor_total_str = partes[idx_valor_total].replace(',', '.')

        try:
            valor_total = float(valor_total_str)
        except:
            valor_total = 0.0

        categoria = ""
        valor_unitario = 0.0
        if pid in dict_produtos:
            produto = dict_produtos[pid]
            categoria = produto.get('categoria', 'OUTROS')
            nome = produto.get('nome', nome)
            valor_unitario = float(produto.get('valor', 0))
        else:
            categoria = "OUTROS"
            if qtd and int(qtd) != 0:
                try:
                    valor_unitario = valor_total / int(qtd)
                except:
                    valor_unitario = 0.0
            else:
                valor_unitario = valor_total

        valor_unitario_str = f"{valor_unitario:.2f}".replace('.', ',')
        valor_total_str = f"{valor_total:.2f}".replace('.', ',')
        categoria_limpa = categoria.replace(';', ' ') if categoria else "OUTROS"
        nome_limpo = nome.replace(';', ' ')

        novas_linhas.append(
            f"{data_hora};{pid};{nome_limpo};{categoria_limpa};{qtd};{valor_unitario_str};{valor_total_str}\n"
        )

    with open(ARQUIVO_VENDAS_ACUMULADAS, 'w', encoding='utf-8') as f:
        f.writelines(novas_linhas)

    print(f"🔄 Arquivo {ARQUIVO_VENDAS_ACUMULADAS} migrado para o novo formato.")

def gerar_relatorio_diario(data_alvo):
    """
    Gera um relatório diário em TXT com tabelas alinhadas e totais.
    """
    if not os.path.exists(ARQUIVO_VENDAS_ACUMULADAS):
        print("⚠️ Nenhum arquivo de vendas acumuladas encontrado.")
        return

    vendas_dia = []
    with open(ARQUIVO_VENDAS_ACUMULADAS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            # Verifica se a linha tem todas as colunas necessárias
            if len(row) < 7:
                continue
            # Verifica se VALOR_TOTAL é um número válido
            valor_str = row.get('VALOR_TOTAL', '0').replace(',', '.')
            try:
                float(valor_str)
            except (ValueError, TypeError):
                continue
            if valor_str in ('0', '0.00'):
                continue
            data_venda = row.get('DATA_HORA', '')[:10]
            if data_venda == data_alvo:
                vendas_dia.append(row)

    if not vendas_dia:
        print(f"ℹ️ Nenhuma venda registrada em {data_alvo}.")
        return

    # Agregar por produto
    por_produto = {}
    for v in vendas_dia:
        pid = v.get('ID', '?')
        nome = v.get('NOME', '')
        if not nome:
            nome = "(Produto removido)"
        qtd = int(v.get('QUANTIDADE_VENDIDA', 0) or 0)
        valor_str = v.get('VALOR_TOTAL', '0').replace(',', '.')
        valor_total = float(valor_str)

        chave = (pid, nome)
        if chave not in por_produto:
            por_produto[chave] = {'qtd': 0, 'valor': 0.0}
        por_produto[chave]['qtd'] += qtd
        por_produto[chave]['valor'] += valor_total

    # Agregar por categoria
    por_categoria = {}
    for v in vendas_dia:
        categoria = v.get('CATEGORIA', 'OUTROS')
        if not categoria:
            categoria = 'OUTROS'
        qtd = int(v.get('QUANTIDADE_VENDIDA', 0) or 0)
        valor_str = v.get('VALOR_TOTAL', '0').replace(',', '.')
        valor_total = float(valor_str)

        if categoria not in por_categoria:
            por_categoria[categoria] = {'qtd': 0, 'valor': 0.0}
        por_categoria[categoria]['qtd'] += qtd
        por_categoria[categoria]['valor'] += valor_total

    total_qtd = sum(p['qtd'] for p in por_produto.values())
    total_valor = sum(p['valor'] for p in por_produto.values())

    nome_arquivo = f"relatorio_diario_{data_alvo}.txt"
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        linha = "=" * 70
        f.write(f"{linha}\n")
        f.write(f"RELATÓRIO DIÁRIO DE VENDAS - {data_alvo}\n")
        f.write(f"{linha}\n\n")
        f.write(f"Total de unidades vendidas: {total_qtd}\n")
        f.write(f"Valor total vendido: {formatar_moeda(total_valor)}\n\n")

        f.write("VENDAS POR PRODUTO\n")
        f.write("-" * 70 + "\n")
        f.write(f"{'ID':<6} {'Produto':<40} {'Qtd':>5} {'Valor Total':>12}\n")
        f.write("-" * 70 + "\n")
        for (pid, nome), dados in sorted(por_produto.items(), key=lambda x: -x[1]['qtd']):
            nome_exib = nome[:38] + '..' if len(nome) > 40 else nome
            f.write(f"{pid:<6} {nome_exib:<40} {dados['qtd']:>5} {formatar_moeda(dados['valor']):>12}\n")
        f.write("-" * 70 + "\n\n")

        f.write("VENDAS POR CATEGORIA\n")
        f.write("-" * 70 + "\n")
        f.write(f"{'Categoria':<40} {'Qtd':>5} {'Valor Total':>12}\n")
        f.write("-" * 70 + "\n")
        for categoria, dados in sorted(por_categoria.items(), key=lambda x: -x[1]['qtd']):
            categoria_exib = categoria[:38] + '..' if len(categoria) > 40 else categoria
            f.write(f"{categoria_exib:<40} {dados['qtd']:>5} {formatar_moeda(dados['valor']):>12}\n")
        f.write("-" * 70 + "\n\n")

        f.write(f"Gerado em: {datetime.now(FUSO_HORARIO).strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write(f"{linha}\n")

    print(f"📊 Relatório diário TXT gerado: {nome_arquivo}")

    gerar_relatorio_diario_html(data_alvo, por_produto, por_categoria, total_qtd, total_valor)
    gerar_relatorio_diario_markdown(data_alvo, por_produto, por_categoria, total_qtd, total_valor)

def gerar_relatorio_diario_html(data_alvo, por_produto, por_categoria, total_qtd, total_valor):
    """
    Gera um relatório diário em HTML com estilo visual agradável.
    """
    nome_arquivo = f"relatorio_diario_{data_alvo}.html"

    linhas_produtos = ""
    for (pid, nome), dados in sorted(por_produto.items(), key=lambda x: -x[1]['qtd']):
        linhas_produtos += f"<tr><td>{pid}</td><td>{nome}</td><td>{dados['qtd']}</td><td>{formatar_moeda(dados['valor'])}</td></tr>\n"

    linhas_categorias = ""
    for categoria, dados in sorted(por_categoria.items(), key=lambda x: -x[1]['qtd']):
        linhas_categorias += f"<tr><td>{categoria}</td><td>{dados['qtd']}</td><td>{formatar_moeda(dados['valor'])}</td></tr>\n"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Relatório Diário de Vendas - {data_alvo}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; background-color: #fff; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .total {{ font-weight: bold; font-size: 1.2em; }}
    </style>
</head>
<body>
    <h1>Relatório Diário de Vendas - {data_alvo}</h1>
    <p class="total">Total de unidades vendidas: {total_qtd}</p>
    <p class="total">Valor total vendido: {formatar_moeda(total_valor)}</p>

    <h2>Vendas por Produto</h2>
    <table>
        <tr><th>ID</th><th>Produto</th><th>Quantidade</th><th>Valor Total</th></tr>
        {linhas_produtos}
    </table>

    <h2>Vendas por Categoria</h2>
    <table>
        <tr><th>Categoria</th><th>Quantidade</th><th>Valor Total</th></tr>
        {linhas_categorias}
    </table>
</body>
</html>"""

    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"🖥️ Relatório diário HTML gerado: {nome_arquivo}")

def gerar_relatorio_diario_markdown(data_alvo, por_produto, por_categoria, total_qtd, total_valor):
    """
    Gera um relatório diário em Markdown (.md) para visualização bonita no GitHub.
    """
    nome_arquivo = f"relatorio_diario_{data_alvo}.md"

    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        f.write(f"# 📊 Relatório Diário de Vendas - {data_alvo}\n\n")
        f.write(f"**Total de unidades vendidas:** {total_qtd}\n")
        f.write(f"**Valor total vendido:** {formatar_moeda(total_valor)}\n\n")

        f.write("## 🛒 Vendas por Produto\n\n")
        f.write("| ID | Produto | Quantidade | Valor Total |\n")
        f.write("|----|---------|-----------:|------------:|\n")
        for (pid, nome), dados in sorted(por_produto.items(), key=lambda x: -x[1]['qtd']):
            f.write(f"| {pid} | {nome} | {dados['qtd']} | {formatar_moeda(dados['valor'])} |\n")
        f.write("\n")

        f.write("## 🏷️ Vendas por Categoria\n\n")
        f.write("| Categoria | Quantidade | Valor Total |\n")
        f.write("|-----------|-----------:|------------:|\n")
        for categoria, dados in sorted(por_categoria.items(), key=lambda x: -x[1]['qtd']):
            f.write(f"| {categoria} | {dados['qtd']} | {formatar_moeda(dados['valor'])} |\n")
        f.write("\n")

        f.write(f"*Gerado em {datetime.now(FUSO_HORARIO).strftime('%d/%m/%Y %H:%M:%S')}*\n")

    print(f"📝 Relatório diário Markdown gerado: {nome_arquivo}")

def gerar_resumo_geral_markdown(arquivo_csv=ARQUIVO_VENDAS_ACUMULADAS):
    """
    Gera um resumo geral das vendas acumuladas em Markdown (.md)
    com visual bonito e organizado.
    """
    if not os.path.exists(arquivo_csv):
        print("⚠️ Nenhum arquivo de vendas acumuladas para resumir.")
        return

    with open(arquivo_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        linhas = []
        for row in reader:
            # Ignora linhas com número incorreto de colunas
            if len(row) < 7:
                continue
            # Tenta converter VALOR_TOTAL, se falhar ignora a linha
            valor_str = row.get('VALOR_TOTAL', '0').replace(',', '.')
            try:
                float(valor_str)
            except (ValueError, TypeError):
                continue
            if valor_str in ('0', '0.00'):
                continue
            linhas.append(row)

    if not linhas:
        print("ℹ️ Nenhuma venda válida para gerar resumo.")
        return

    por_produto = {}
    por_categoria = {}
    por_dia = {}

    for v in linhas:
        pid = v.get('ID', '?')
        nome = v.get('NOME', '(Produto removido)')
        categoria = v.get('CATEGORIA', 'OUTROS')
        data = v.get('DATA_HORA', '')[:10]
        qtd = int(v.get('QUANTIDADE_VENDIDA', 0) or 0)
        valor_total = float(v.get('VALOR_TOTAL', '0').replace(',', '.') or 0)

        chave_produto = (pid, nome)
        por_produto.setdefault(chave_produto, {'qtd': 0, 'valor': 0.0})
        por_produto[chave_produto]['qtd'] += qtd
        por_produto[chave_produto]['valor'] += valor_total

        por_categoria.setdefault(categoria, {'qtd': 0, 'valor': 0.0})
        por_categoria[categoria]['qtd'] += qtd
        por_categoria[categoria]['valor'] += valor_total

        por_dia.setdefault(data, {'qtd': 0, 'valor': 0.0})
        por_dia[data]['qtd'] += qtd
        por_dia[data]['valor'] += valor_total

    total_unidades = sum(p['qtd'] for p in por_produto.values())
    total_valor = sum(p['valor'] for p in por_produto.values())

    nome_arquivo = "vendas_acumuladas_resumo.md"
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        f.write("# 📊 Resumo de Vendas Acumuladas\n\n")
        f.write(f"**Total de unidades vendidas:** {total_unidades}\n\n")
        f.write(f"**Valor total vendido:** {formatar_moeda(total_valor)}\n\n")

        f.write("## 🏷️ Vendas por Categoria\n\n")
        f.write("| Categoria | Quantidade | Valor Total |\n")
        f.write("|-----------|-----------:|------------:|\n")
        for categoria, dados in sorted(por_categoria.items(), key=lambda x: -x[1]['qtd']):
            f.write(f"| {categoria} | {dados['qtd']} | {formatar_moeda(dados['valor'])} |\n")
        f.write("\n")

        f.write("## 🛒 Top 20 Produtos Mais Vendidos\n\n")
        f.write("| ID | Produto | Quantidade | Valor Total |\n")
        f.write("|----|---------|-----------:|------------:|\n")
        produtos_ordenados = sorted(por_produto.items(), key=lambda x: -x[1]['qtd'])[:20]
        for (pid, nome), dados in produtos_ordenados:
            f.write(f"| {pid} | {nome} | {dados['qtd']} | {formatar_moeda(dados['valor'])} |\n")
        f.write("\n")

        f.write("## 📅 Vendas por Dia\n\n")
        f.write("| Data | Quantidade | Valor Total |\n")
        f.write("|------|-----------:|------------:|\n")
        for data in sorted(por_dia.keys()):
            dados = por_dia[data]
            f.write(f"| {data} | {dados['qtd']} | {formatar_moeda(dados['valor'])} |\n")
        f.write("\n")

        f.write(f"*Última atualização: {datetime.now(FUSO_HORARIO).strftime('%d/%m/%Y %H:%M:%S')}*\n")

    print(f"🖥️ Resumo geral em Markdown gerado: {nome_arquivo}")

def obter_data_local_snapshot(snapshot):
    """Extrai a data local (YYYY-MM-DD) de um snapshot."""
    timestamp_iso = snapshot.get('timestamp_iso')
    if timestamp_iso:
        dt = datetime.fromisoformat(timestamp_iso)
        return dt.astimezone(FUSO_HORARIO).strftime("%Y-%m-%d")
    ts = snapshot.get('timestamp', '')
    if ts:
        try:
            dt_utc = datetime.strptime(ts, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            return dt_utc.astimezone(FUSO_HORARIO).strftime("%Y-%m-%d")
        except:
            pass
    return None

def main():
    print("=" * 80)
    print("🚀 MONITORAMENTO DE CATÁLOGO E VENDAS")
    print("=" * 80)

    api = CatalogoAPI()

    print("\n🔍 Buscando catálogo...")
    catalogo = api.buscar_catalogo_completo()
    if not catalogo.get('success', True):
        print(f"❌ Erro ao buscar catálogo: {catalogo.get('error', 'Desconhecido')}")
        return

    produtos = api.extrair_produtos(catalogo)
    print(f"✅ {len(produtos)} produtos encontrados")

    # Migrar vendas acumuladas se necessário
    migrar_vendas_acumuladas(produtos)

    com_estoque = [p for p in produtos if p.get('estoque') is not None and int(p['estoque']) > 0]
    print(f"📦 Produtos com estoque > 0: {len(com_estoque)}")

    snap_anterior = carregar_ultimo_snapshot()

    # Verifica virada de dia e gera relatório diário
    data_local_atual = datetime.now(FUSO_HORARIO).strftime("%Y-%m-%d")
    if snap_anterior:
        data_snapshot_anterior = obter_data_local_snapshot(snap_anterior)
        if data_snapshot_anterior and data_snapshot_anterior != data_local_atual:
            print(f"\n🔄 Virada de dia detectada: {data_snapshot_anterior} → {data_local_atual}")
            gerar_relatorio_diario(data_snapshot_anterior)

    arquivo_snapshot = salvar_snapshot(com_estoque)
    print(f"💾 Snapshot salvo em: {arquivo_snapshot}")

    if snap_anterior:
        vendas, reposicoes, sem_mudanca = gerar_relatorio_vendas(snap_anterior, com_estoque)
        print("\n" + "=" * 80)
        print("📈 RELATÓRIO DE VENDAS (desde a última execução)")
        print("=" * 80)
        print(f"Produtos sem mudança: {sem_mudanca}")
        print(f"Produtos vendidos: {len(vendas)}")
        print(f"Produtos repostos: {len(reposicoes)}")

        if vendas:
            print("\n--- VENDAS ---")
            for v in vendas:
                print(f"{v['unidades']:>4} un. | {v['nome']} (ID {v['id']}) | anterior: {v['qtd_anterior']}, atual: {v['qtd_atual']} | valor: {formatar_moeda(v['valor_total'])}")
            registrar_vendas_acumuladas(vendas)

        if reposicoes:
            print("\n--- REPOSIÇÕES ---")
            for r in reposicoes:
                print(f"+{r['unidades']:>4} un. | {r['nome']} (ID {r['id']}) | anterior: {r['qtd_anterior']}, atual: {r['qtd_atual']} | valor: {formatar_moeda(r['valor_total'])}")

        total_vendido = sum(v['unidades'] for v in vendas)
        total_comprado = sum(r['unidades'] for r in reposicoes)
        valor_vendido = sum(v['valor_total'] for v in vendas)
        valor_comprado = sum(r['valor_total'] for r in reposicoes)

        print("\n" + "=" * 80)
        print("📊 RESUMO DE MOVIMENTAÇÕES")
        print("=" * 80)
        print(f"Unidades vendidas: {total_vendido}")
        print(f"Valor total vendido: {formatar_moeda(valor_vendido)}")
        print(f"Unidades repostas (compradas): {total_comprado}")
        print(f"Valor total reposto: {formatar_moeda(valor_comprado)}")

        with open('movimentacoes.csv', 'w', encoding='utf-8') as f:
            f.write("TIPO;ID;NOME;CATEGORIA;UNIDADES;VALOR_UNITARIO;VALOR_TOTAL;QTD_ANTERIOR;QTD_ATUAL\n")
            for v in vendas:
                f.write(f"VENDA;{v['id']};{v['nome']};{v['categoria']};{v['unidades']};{v['valor_unit']};{v['valor_total']};{v['qtd_anterior']};{v['qtd_atual']}\n")
            for r in reposicoes:
                f.write(f"REPOSICAO;{r['id']};{r['nome']};{r['categoria']};{r['unidades']};{r['valor_unit']};{r['valor_total']};{r['qtd_anterior']};{r['qtd_atual']}\n")
        print("📁 CSV de movimentações salvo: movimentacoes.csv")
    else:
        print("\n📌 Primeira execução: nenhum snapshot anterior para comparar.")

    # Agrupar por categoria para exibição
    categorias = {}
    for p in com_estoque:
        cat = p.get('categoria', 'OUTROS')
        categorias.setdefault(cat, []).append(p)

    print("\n" + "=" * 80)
    print("📋 CATÁLOGO ORGANIZADO POR CATEGORIA")
    print("=" * 80)

    total_geral = 0
    valor_geral = 0.0

    for categoria in sorted(categorias.keys()):
        produtos_cat = sorted(categorias[categoria], key=lambda x: x.get('nome', '').lower())
        qtd_cat = len(produtos_cat)
        valor_cat = sum(float(p.get('valor', 0)) for p in produtos_cat)
        total_geral += qtd_cat
        valor_geral += valor_cat

        print(f"\n📂 {categoria}  ({qtd_cat} produtos)")
        print("-" * 80)
        print(f"{'ID':<6} {'Nome':<40} {'Qtd':>5} {'Valor':>10}")
        print("-" * 80)

        for p in produtos_cat:
            id_str = str(p.get('id', ''))
            nome = p.get('nome', p.get('descricao', ''))
            qtd = int(p.get('estoque', 0))
            valor = float(p.get('valor', 0))
            nome_exib = nome[:38] + '..' if len(nome) > 40 else nome
            print(f"{id_str:<6} {nome_exib:<40} {qtd:>5} {formatar_moeda(valor):>10}")

        print(f"{'':<6} {'Total da categoria':<40} {qtd_cat:>5} {formatar_moeda(valor_cat):>10}")

    print("\n" + "=" * 80)
    print(f"TOTAL GERAL: {total_geral} produtos | Valor total: {formatar_moeda(valor_geral)}")
    print("=" * 80)

    with open('catalogo_por_categoria.csv', 'w', encoding='utf-8') as f:
        f.write("CATEGORIA;ID;NOME;QUANTIDADE;VALOR\n")
        for categoria in sorted(categorias.keys()):
            for p in sorted(categorias[categoria], key=lambda x: x.get('nome', '').lower()):
                f.write(f"{categoria};{p['id']};{p.get('nome','')};{p.get('estoque', 0)};{p.get('valor', 0)}\n")
    print("\n📁 CSV por categoria salvo: catalogo_por_categoria.csv")

    with open('catalogo_geral.csv', 'w', encoding='utf-8') as f:
        f.write("ID;NOME;QUANTIDADE;VALOR;CATEGORIA\n")
        for p in sorted(com_estoque, key=lambda x: int(x.get('id', 0))):
            f.write(f"{p['id']};{p.get('nome','')};{p.get('estoque', 0)};{p.get('valor', 0)};{p.get('categoria','')}\n")
    print("📁 CSV geral salvo: catalogo_geral.csv")

    # Gerar resumo geral em Markdown
    gerar_resumo_geral_markdown()

    print("\n✅ Execução concluída!")

if __name__ == "__main__":
    main()