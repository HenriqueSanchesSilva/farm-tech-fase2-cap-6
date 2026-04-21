import os
import json
from datetime import datetime
from pathlib import Path
import oracledb
from dotenv import load_dotenv

load_dotenv()

# Categorias de insumos e unidades de medida
CATEGORIAS = ("Fertilizante", "Defensivo", "Semente")
UNIDADES = ("kg", "L", "saco", "unidade")

# Valores default de limiares de estoque
LIMIAR_ESTOQUE_CRITICO = 5
LIMIAR_ESTOQUE_BAIXO = 15
LIMIAR_ESTOQUE_IDEAL = 50

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ARQUIVO_JSON = DATA_DIR / "insumos.json"
ARQUIVO_LOG = DATA_DIR / "movimentacoes.txt"

# margem para mensagens de console (para melhor formatação)
MARGEM = " " * 4

# Credenciais Oracle carregadas de variáveis de ambiente (.env)
ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_DSN = os.getenv("ORACLE_DSN", "oracle.fiap.com.br:1521/ORCL")

# Para saber se Oracle conectou 
conn = None

## Funções genéricas de interface e leitura de dados

class VoltarOperacao(Exception):
    pass

class CancelarOperacao(Exception):
    pass

def limpar_tela() -> None:
    os.system("cls" if os.name == "nt" else "clear")

def pausar() -> None:
    input(f"\n{MARGEM}Pressione ENTER para continuar...")

def linha(caractere: str = "-", tamanho: int = 60) -> None:
    print(caractere * tamanho)

def ler_entrada(mensagem: str, permitir_navegacao: bool = False) -> str:
    valor = input(mensagem).strip()
    if permitir_navegacao:
        comando = valor.lower()
        if comando == "voltar":
            raise VoltarOperacao()
        if comando == "sair":
            raise CancelarOperacao()
    return valor

def ler_inteiro(mensagem: str, permitir_navegacao: bool = False) -> int:
    while True:
        try:
            return int(ler_entrada(mensagem, permitir_navegacao))
        except ValueError:
            print(f"{MARGEM}Erro: digite um número inteiro válido.")

def ler_float(mensagem: str, permitir_navegacao: bool = False) -> float:
    while True:
        try:
            valor = float(ler_entrada(mensagem, permitir_navegacao))
            if valor < 0:
                print(f"{MARGEM}Erro: o valor não pode ser negativo.")
                continue
            return valor
        except ValueError:
            print(f"{MARGEM}Erro: digite um número válido.")

def ler_texto(mensagem: str, permitir_navegacao: bool = False) -> str:
    while True:
        texto = ler_entrada(mensagem, permitir_navegacao)
        if texto:
            return texto
        print(f"{MARGEM}Erro: campo obrigatório.")

def escolher_opcao(titulo: str, opcoes: tuple, permitir_navegacao: bool = False) -> str:
    print(f"\n{MARGEM}{titulo}")
    for i, item in enumerate(opcoes, 1):
        print(f"{MARGEM}  {i} - {item}")
    while True:
        escolha = ler_inteiro(f"{MARGEM}Escolha (1-{len(opcoes)}): ", permitir_navegacao)
        if 1 <= escolha <= len(opcoes):
            return opcoes[escolha - 1]
        print(f"{MARGEM}Opção inválida.")

def gerar_id(tabela: list) -> int:
    if not tabela:
        return 1
    return max(item["id"] for item in tabela) + 1

## Funções específicas do domínio de insumos e estoque (para clasficar o nivel e exibir para o usuario)
def classificar_estoque(quantidade: float, critico: float = None,
                        baixo: float = None, ideal: float = None) -> str:
    critico = critico if critico is not None else LIMIAR_ESTOQUE_CRITICO
    baixo = baixo if baixo is not None else LIMIAR_ESTOQUE_BAIXO
    ideal = ideal if ideal is not None else LIMIAR_ESTOQUE_IDEAL
    if quantidade <= critico:
        return "CRITICO"
    elif quantidade <= baixo:
        return "BAIXO"
    elif quantidade <= ideal:
        return "ADEQUADO"
    return "ALTO"

def status_insumo(insumo: dict) -> str:
    return classificar_estoque(
        insumo["quantidade"],
        insumo.get("limiar_critico"),
        insumo.get("limiar_baixo"),
        insumo.get("limiar_ideal")
    )

def icone_estoque(status: str) -> str:
    icones = {
        "CRITICO": "[!!!]",
        "BAIXO": "[! ]",
        "ADEQUADO": "[ + ]",
        "ALTO": "[+++]"
    }
    return icones.get(status, "[   ]")


## Conexão e operações com Oracle Database

def conectar_oracle() -> bool:
    global conn
    if not ORACLE_USER or not ORACLE_PASSWORD:
        print(f"{MARGEM}Credenciais Oracle não configuradas (.env ausente ou incompleto).")
        print(f"{MARGEM}Continuando com persistência local (JSON/TXT).")
        return False
    try:
        conn = oracledb.connect(
            user=ORACLE_USER,
            password=ORACLE_PASSWORD,
            dsn=ORACLE_DSN
        )
        print(f"{MARGEM}Conectado ao Oracle com sucesso!")
        return True
    except Exception as e:
        print(f"{MARGEM}Erro ao conectar no Oracle: {e}")
        print(f"{MARGEM}Continuando com persistência local (JSON/TXT).")
        return False

def desconectar_oracle() -> None:
    global conn
    if conn:
        try:
            conn.close()
        except Exception:
            pass
        conn = None

def criar_tabelas() -> None:
    ## Tenta criar as tabelas necessárias no Oracle, ignorando erros de "tabela já existe" que é o código 955
    cursor = conn.cursor()
    try:
        try:
            cursor.execute("""
                CREATE TABLE insumos (
                    id NUMBER PRIMARY KEY,
                    nome VARCHAR2(100) NOT NULL,
                    categoria VARCHAR2(50) NOT NULL,
                    unidade VARCHAR2(20) NOT NULL,
                    quantidade NUMBER(10,2) NOT NULL,
                    preco NUMBER(10,2) NOT NULL,
                    fornecedor VARCHAR2(100) NOT NULL,
                    data_cadastro VARCHAR2(10) NOT NULL,
                    limiar_critico NUMBER(10,2) DEFAULT 5,
                    limiar_baixo NUMBER(10,2) DEFAULT 15,
                    limiar_ideal NUMBER(10,2) DEFAULT 50
                )
            """)
        except oracledb.DatabaseError as e:
            if e.args[0].code != 955:
                raise
        for col_def in [
            "limiar_critico NUMBER(10,2) DEFAULT 5",
            "limiar_baixo NUMBER(10,2) DEFAULT 15",
            "limiar_ideal NUMBER(10,2) DEFAULT 50",
        ]:
            try:
                cursor.execute(f"ALTER TABLE insumos ADD {col_def}")
            except oracledb.DatabaseError:
                pass
        try:
            cursor.execute("""
                CREATE TABLE movimentacoes (
                    data_hora VARCHAR2(20) NOT NULL,
                    tipo VARCHAR2(20) NOT NULL,
                    descricao VARCHAR2(500) NOT NULL
                )
            """)
        except oracledb.DatabaseError as e:
            if e.args[0].code != 955:
                raise
        conn.commit()
    finally:
        cursor.close()

def inserir_insumo_db(insumo: dict) -> bool:
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO insumos
               (id, nome, categoria, unidade, quantidade, preco, fornecedor, data_cadastro,
                limiar_critico, limiar_baixo, limiar_ideal)
               VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11)""",
            [insumo["id"], insumo["nome"], insumo["categoria"], insumo["unidade"],
             insumo["quantidade"], insumo["preco"], insumo["fornecedor"], insumo["data_cadastro"],
             insumo.get("limiar_critico", LIMIAR_ESTOQUE_CRITICO),
             insumo.get("limiar_baixo", LIMIAR_ESTOQUE_BAIXO),
             insumo.get("limiar_ideal", LIMIAR_ESTOQUE_IDEAL)]
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"{MARGEM}Erro Oracle (insert): {e}")
        return False
    finally:
        cursor.close()

def atualizar_insumo_db(insumo: dict) -> bool:
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE insumos
               SET nome = :1, categoria = :2, unidade = :3, preco = :4, fornecedor = :5,
                   limiar_critico = :6, limiar_baixo = :7, limiar_ideal = :8
               WHERE id = :9""",
            [insumo["nome"], insumo["categoria"], insumo["unidade"],
             insumo["preco"], insumo["fornecedor"],
             insumo.get("limiar_critico", LIMIAR_ESTOQUE_CRITICO),
             insumo.get("limiar_baixo", LIMIAR_ESTOQUE_BAIXO),
             insumo.get("limiar_ideal", LIMIAR_ESTOQUE_IDEAL),
             insumo["id"]]
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"{MARGEM}Erro Oracle (update): {e}")
        return False
    finally:
        cursor.close()

def atualizar_quantidade_db(insumo_id: int, nova_quantidade: float) -> bool:
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE insumos SET quantidade = :1 WHERE id = :2",
            [nova_quantidade, insumo_id]
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"{MARGEM}Erro Oracle (update qtd): {e}")
        return False
    finally:
        cursor.close()

def excluir_insumo_db(insumo_id: int) -> bool:
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM insumos WHERE id = :1", [insumo_id])
        conn.commit()
        return True
    except Exception as e:
        print(f"{MARGEM}Erro Oracle (delete): {e}")
        return False
    finally:
        cursor.close()

def salvar_dados(tabela: list) -> bool:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(ARQUIVO_JSON, "w", encoding="utf-8") as arq:
            json.dump(tabela, arq, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"{MARGEM}Erro ao salvar: {e}")
        return False

def carregar_dados() -> list:
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, nome, categoria, unidade, quantidade, preco, "
                "fornecedor, data_cadastro, limiar_critico, limiar_baixo, "
                "limiar_ideal FROM insumos ORDER BY id"
            )
            tabela = []
            for row in cursor:
                tabela.append({
                    "id": int(row[0]),
                    "nome": row[1],
                    "categoria": row[2],
                    "unidade": row[3],
                    "quantidade": float(row[4]),
                    "preco": float(row[5]),
                    "fornecedor": row[6],
                    "data_cadastro": row[7],
                    "limiar_critico": float(row[8]) if row[8] is not None else LIMIAR_ESTOQUE_CRITICO,
                    "limiar_baixo": float(row[9]) if row[9] is not None else LIMIAR_ESTOQUE_BAIXO,
                    "limiar_ideal": float(row[10]) if row[10] is not None else LIMIAR_ESTOQUE_IDEAL
                })
            return tabela
        except Exception as e:
            print(f"{MARGEM}Erro ao carregar do Oracle: {e}")
        finally:
            cursor.close()
    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as arq:
            return json.load(arq)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        print(f"{MARGEM}Aviso: JSON corrompido. Iniciando base vazia.")
        return []

def gravar_log(tipo: str, descricao: str) -> None:
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO movimentacoes (data_hora, tipo, descricao) "
                "VALUES (:1, :2, :3)",
                [ts, tipo, descricao]
            )
            conn.commit()
        except Exception as e:
            print(f"{MARGEM}Aviso: falha ao gravar log no Oracle: {e}")
        finally:
            cursor.close()
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(ARQUIVO_LOG, "a", encoding="utf-8") as arq:
            arq.write(f"{ts}|{tipo}|{descricao}\n")
    except Exception:
        pass

def carregar_log() -> list:
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT data_hora, tipo, descricao FROM movimentacoes ORDER BY ROWID"
            )
            registros = []
            for row in cursor:
                registros.append({
                    "timestamp": row[0],
                    "tipo": row[1],
                    "descricao": row[2]
                })
            return registros
        except Exception:
            pass
        finally:
            cursor.close()
    registros = []
    try:
        with open(ARQUIVO_LOG, "r", encoding="utf-8") as arq:
            for linha_log in arq.readlines():
                partes = linha_log.strip().split("|")
                if len(partes) >= 3:
                    registros.append({
                        "timestamp": partes[0],
                        "tipo": partes[1],
                        "descricao": "|".join(partes[2:])
                    })
    except FileNotFoundError:
        pass
    return registros

def encontrar_por_id(tabela: list, id_busca: int) -> dict:
    for item in tabela:
        if item["id"] == id_busca:
            return item
    return None

def exibir_detalhe(insumo: dict) -> None:
    status = status_insumo(insumo)
    valor_total = insumo["quantidade"] * insumo["preco"]
    lc = insumo.get('limiar_critico', LIMIAR_ESTOQUE_CRITICO)
    lb = insumo.get('limiar_baixo', LIMIAR_ESTOQUE_BAIXO)
    li = insumo.get('limiar_ideal', LIMIAR_ESTOQUE_IDEAL)
    print(f"{MARGEM}ID...............: {insumo['id']}")
    print(f"{MARGEM}Nome.............: {insumo['nome']}")
    print(f"{MARGEM}Categoria........: {insumo['categoria']}")
    print(f"{MARGEM}Quantidade.......: {insumo['quantidade']:.2f} {insumo['unidade']}")
    print(f"{MARGEM}Preço unitário...: R$ {insumo['preco']:.2f}")
    print(f"{MARGEM}Valor em estoque.: R$ {valor_total:.2f}")
    print(f"{MARGEM}Fornecedor.......: {insumo['fornecedor']}")
    print(f"{MARGEM}Status estoque...: {icone_estoque(status)} {status}")
    print(f"{MARGEM}Limiares.........: Crítico ≤{lc:.0f} | Baixo ≤{lb:.0f} | Ideal ≤{li:.0f}")
    linha("-", 50)

# Funções de cada operação do menu (cadastrar, listar, buscar, atualizar, excluir, registrar entrada/saída)

def cadastrar(tabela: list) -> None:
    limpar_tela()
    linha("=")
    print("  CADASTRAR NOVO INSUMO")
    linha("=")

    print(f"\n{MARGEM}Digite 'voltar' para retornar uma etapa ou 'sair' para cancelar.\n")

    etapas = ["nome", "categoria", "unidade", "quantidade", "preco", "fornecedor",
              "limiar_critico", "limiar_baixo", "limiar_ideal"]
    dados = {}
    indice = 0

    while indice < len(etapas):
        etapa = etapas[indice]
        try:
            if etapa == "nome":
                dados["nome"] = ler_texto(f"{MARGEM}Nome do insumo......: ", True)
            elif etapa == "categoria":
                dados["categoria"] = escolher_opcao("Categorias:", CATEGORIAS, True)
            elif etapa == "unidade":
                dados["unidade"] = escolher_opcao("Unidades de medida:", UNIDADES, True)
            elif etapa == "quantidade":
                qtd = ler_float(f"{MARGEM}Quantidade inicial..: ", True)
                if qtd <= 0:
                    print(f"{MARGEM}Erro: quantidade deve ser maior que zero.")
                    continue
                dados["quantidade"] = qtd
            elif etapa == "preco":
                dados["preco"] = ler_float(f"{MARGEM}Preço unitário (R$).: ", True)
            elif etapa == "fornecedor":
                dados["fornecedor"] = ler_texto(f"{MARGEM}Fornecedor..........: ", True)
            elif etapa == "limiar_critico":
                print(f"\n{MARGEM}Limiares de estoque (ENTER = padrão):")
                val = ler_entrada(f"{MARGEM}  Crítico [{LIMIAR_ESTOQUE_CRITICO}]......: ", True)
                if val:
                    try:
                        dados["limiar_critico"] = float(val)
                    except ValueError:
                        print(f"{MARGEM}Valor inválido.")
                        continue
                else:
                    dados["limiar_critico"] = float(LIMIAR_ESTOQUE_CRITICO)
            elif etapa == "limiar_baixo":
                val = ler_entrada(f"{MARGEM}  Baixo [{LIMIAR_ESTOQUE_BAIXO}]........: ", True)
                if val:
                    try:
                        dados["limiar_baixo"] = float(val)
                    except ValueError:
                        print(f"{MARGEM}Valor inválido.")
                        continue
                else:
                    dados["limiar_baixo"] = float(LIMIAR_ESTOQUE_BAIXO)
            elif etapa == "limiar_ideal":
                val = ler_entrada(f"{MARGEM}  Ideal [{LIMIAR_ESTOQUE_IDEAL}]........: ", True)
                if val:
                    try:
                        dados["limiar_ideal"] = float(val)
                    except ValueError:
                        print(f"{MARGEM}Valor inválido.")
                        continue
                else:
                    dados["limiar_ideal"] = float(LIMIAR_ESTOQUE_IDEAL)
                if dados["limiar_critico"] >= dados["limiar_baixo"] or dados["limiar_baixo"] >= dados["limiar_ideal"]:
                    print(f"{MARGEM}Erro: os limiares devem seguir a ordem Crítico < Baixo < Ideal.")
                    indice = etapas.index("limiar_critico")
                    continue
            indice += 1
        except VoltarOperacao:
            if indice > 0:
                indice -= 1
            else:
                print(f"{MARGEM}Você já está na primeira etapa.")
        except CancelarOperacao:
            print(f"\n{MARGEM}Cadastro cancelado. Retornando ao menu...")
            pausar()
            return

    novo = {
        "id": gerar_id(tabela),
        "nome": dados["nome"],
        "categoria": dados["categoria"],
        "unidade": dados["unidade"],
        "quantidade": dados["quantidade"],
        "preco": dados["preco"],
        "fornecedor": dados["fornecedor"],
        "limiar_critico": dados["limiar_critico"],
        "limiar_baixo": dados["limiar_baixo"],
        "limiar_ideal": dados["limiar_ideal"],
        "data_cadastro": datetime.now().strftime("%d/%m/%Y")
    }

    tabela.append(novo)
    inserir_insumo_db(novo)
    salvar_dados(tabela)
    gravar_log(
        "CADASTRO",
        f"ID={novo['id']}|{novo['nome']}|{novo['quantidade']}{novo['unidade']}|R${novo['preco']:.2f}|{novo['fornecedor']}"
    )
    print(f"\n{MARGEM}Insumo cadastrado com sucesso! (ID: {novo['id']})")
    pausar()

def listar(tabela: list) -> None:
    limpar_tela()
    linha("=")
    print("  INSUMOS CADASTRADOS")
    linha("=")

    if not tabela:
        print(f"\n{MARGEM}Nenhum insumo cadastrado.")
        pausar()
        return

    print(f"\n{'ID':<5} {'Nome':<18} {'Categ.':<13} {'Qtd':>8} {'Un.':<6} {'R$/un':>9} {'Valor tot.':>11} {'Status':<10}")
    linha("-", 82)

    for ins in tabela:
        status = status_insumo(ins)
        valor_total = ins["quantidade"] * ins["preco"]
        nome_exibir = ins['nome'][:17] + "…" if len(ins['nome']) > 18 else ins['nome']
        print(
            f"{ins['id']:<5} "
            f"{nome_exibir:<18} "
            f"{ins['categoria']:<13} "
            f"{ins['quantidade']:>8.1f} "
            f"{ins['unidade']:<6} "
            f"{ins['preco']:>9.2f} "
            f"{valor_total:>11.2f} "
            f"{icone_estoque(status):<10}"
        )

    linha("-", 82)
    total_valor = sum(i["quantidade"] * i["preco"] for i in tabela)
    print(f"{'':>51} TOTAL EM ESTOQUE: R$ {total_valor:>11.2f}")
    print(f"\n{MARGEM}Legenda: [!!!] Crítico  [! ] Baixo  [ + ] Adequado  [+++] Alto")
    pausar()

def buscar(tabela: list) -> None:
    limpar_tela()
    linha("=")
    print("  BUSCAR INSUMO")
    linha("=")

    if not tabela:
        print(f"\n{MARGEM}Nenhum insumo cadastrado.")
        pausar()
        return

    print(f"\n{MARGEM}1 - Buscar por ID")
    print(f"{MARGEM}2 - Buscar por nome")
    print(f"{MARGEM}3 - Buscar por categoria")
    opcao = ler_inteiro(f"{MARGEM}Escolha: ")

    resultados = []

    if opcao == 1:
        resultados = [i for i in tabela if i["id"] == ler_inteiro(f"{MARGEM}ID: ")]
    elif opcao == 2:
        termo = ler_texto(f"{MARGEM}Nome (parcial): ").lower()
        resultados = [i for i in tabela if termo in i["nome"].lower()]
    elif opcao == 3:
        cat = escolher_opcao("Filtrar por:", CATEGORIAS)
        resultados = [i for i in tabela if i["categoria"] == cat]
    else:
        print(f"{MARGEM}Opção inválida.")
        pausar()
        return

    if not resultados:
        print(f"\n{MARGEM}Nenhum resultado encontrado.")
    else:
        print(f"\n{MARGEM}{len(resultados)} resultado(s):\n")
        for ins in resultados:
            exibir_detalhe(ins)
    pausar()

def atualizar(tabela: list) -> None:
    limpar_tela()
    linha("=")
    print("  ATUALIZAR INSUMO")
    linha("=")

    if not tabela:
        print(f"\n{MARGEM}Nenhum insumo cadastrado.")
        pausar()
        return

    insumo = encontrar_por_id(tabela, ler_inteiro(f"\n{MARGEM}ID do insumo: "))
    if not insumo:
        print(f"{MARGEM}Insumo não encontrado.")
        pausar()
        return

    print(f"\n{MARGEM}Dados atuais:")
    exibir_detalhe(insumo)
    print(f"{MARGEM}(ENTER mantém o valor atual)\n")
    print(f"{MARGEM}Digite 'voltar' para retornar uma etapa ou 'sair' para cancelar.\n")

    original = insumo.copy()
    etapas = ["nome", "categoria", "unidade", "preco", "fornecedor",
              "limiar_critico", "limiar_baixo", "limiar_ideal"]
    indice = 0

    while indice < len(etapas):
        etapa = etapas[indice]
        try:
            if etapa == "nome":
                novo_nome = ler_entrada(f"{MARGEM}Nome [{insumo['nome']}]: ", True)
                if novo_nome:
                    insumo["nome"] = novo_nome

            elif etapa == "categoria":
                alt_cat = ler_entrada(
                    f"{MARGEM}Alterar categoria? (s/n) [{insumo['categoria']}]: ",
                    True
                ).lower()
                if alt_cat == "s":
                    insumo["categoria"] = escolher_opcao("Nova categoria:", CATEGORIAS, True)
                elif alt_cat and alt_cat != "n":
                    print(f"{MARGEM}Opção inválida. Digite 's', 'n', 'voltar' ou 'sair'.")
                    continue

            elif etapa == "unidade":
                alt_un = ler_entrada(
                    f"{MARGEM}Alterar unidade? (s/n) [{insumo['unidade']}]: ",
                    True
                ).lower()
                if alt_un == "s":
                    insumo["unidade"] = escolher_opcao("Nova unidade:", UNIDADES, True)
                elif alt_un and alt_un != "n":
                    print(f"{MARGEM}Opção inválida. Digite 's', 'n', 'voltar' ou 'sair'.")
                    continue

            elif etapa == "preco":
                novo_preco = ler_entrada(f"{MARGEM}Preço [{insumo['preco']:.2f}]: ", True)
                if novo_preco:
                    try:
                        v = float(novo_preco)
                        if v < 0:
                            print(f"{MARGEM}Valor inválido, não pode ser negativo.")
                            continue
                        insumo["preco"] = v
                    except ValueError:
                        print(f"{MARGEM}Valor inválido. Digite um número válido.")
                        continue

            elif etapa == "fornecedor":
                novo_forn = ler_entrada(f"{MARGEM}Fornecedor [{insumo['fornecedor']}]: ", True)
                if novo_forn:
                    insumo["fornecedor"] = novo_forn

            elif etapa == "limiar_critico":
                val = ler_entrada(f"{MARGEM}Limiar crítico [{insumo.get('limiar_critico', LIMIAR_ESTOQUE_CRITICO):.0f}]: ", True)
                if val:
                    try:
                        insumo["limiar_critico"] = float(val)
                    except ValueError:
                        print(f"{MARGEM}Valor inválido.")
                        continue
            elif etapa == "limiar_baixo":
                val = ler_entrada(f"{MARGEM}Limiar baixo [{insumo.get('limiar_baixo', LIMIAR_ESTOQUE_BAIXO):.0f}]: ", True)
                if val:
                    try:
                        insumo["limiar_baixo"] = float(val)
                    except ValueError:
                        print(f"{MARGEM}Valor inválido.")
                        continue
            elif etapa == "limiar_ideal":
                val = ler_entrada(f"{MARGEM}Limiar ideal [{insumo.get('limiar_ideal', LIMIAR_ESTOQUE_IDEAL):.0f}]: ", True)
                if val:
                    try:
                        insumo["limiar_ideal"] = float(val)
                    except ValueError:
                        print(f"{MARGEM}Valor inválido.")
                        continue

            lc = insumo.get("limiar_critico", LIMIAR_ESTOQUE_CRITICO)
            lb = insumo.get("limiar_baixo", LIMIAR_ESTOQUE_BAIXO)
            li = insumo.get("limiar_ideal", LIMIAR_ESTOQUE_IDEAL)
            if etapa == "limiar_ideal" and (lc >= lb or lb >= li):
                print(f"{MARGEM}Erro: os limiares devem seguir a ordem Crítico < Baixo < Ideal.")
                indice = etapas.index("limiar_critico")
                continue

            indice += 1

        except VoltarOperacao:
            if indice > 0:
                indice -= 1
            else:
                print(f"{MARGEM}Você já está na primeira etapa.")
        except CancelarOperacao:
            insumo.update(original)
            print(f"\n{MARGEM}Atualização cancelada. Retornando ao menu...")
            pausar()
            return

    atualizar_insumo_db(insumo)
    salvar_dados(tabela)
    gravar_log("ATUALIZACAO", f"ID={insumo['id']}|{insumo['nome']}")
    print(f"\n{MARGEM}Insumo atualizado!")
    pausar()

def excluir(tabela: list) -> None:
    limpar_tela()
    linha("=")
    print("  EXCLUIR INSUMO")
    linha("=")

    if not tabela:
        print(f"\n{MARGEM}Nenhum insumo cadastrado.")
        pausar()
        return

    insumo = encontrar_por_id(tabela, ler_inteiro(f"\n{MARGEM}ID do insumo: "))
    if not insumo:
        print(f"{MARGEM}Insumo não encontrado.")
        pausar()
        return

    exibir_detalhe(insumo)
    if ler_entrada(f"{MARGEM}Confirma exclusão? (s/n): ").lower() == "s":
        nome = insumo["nome"]
        id_excluido = insumo["id"]
        tabela.remove(insumo)
        excluir_insumo_db(id_excluido)
        salvar_dados(tabela)
        gravar_log("EXCLUSAO", f"ID={id_excluido}|{nome}")
        print(f"\n{MARGEM}Insumo excluído!")
    else:
        print(f"\n{MARGEM}Cancelado.")
    pausar()

def registrar_entrada(tabela: list) -> None:
    limpar_tela()
    linha("=")
    print("  ENTRADA DE ESTOQUE")
    linha("=")

    if not tabela:
        print(f"\n{MARGEM}Nenhum insumo cadastrado.")
        pausar()
        return

    insumo = encontrar_por_id(tabela, ler_inteiro(f"\n{MARGEM}ID do insumo: "))
    if not insumo:
        print(f"{MARGEM}Insumo não encontrado.")
        pausar()
        return

    print(f"\n{MARGEM}{insumo['nome']} — Estoque atual: {insumo['quantidade']:.2f} {insumo['unidade']}")
    qtd = ler_float(f"{MARGEM}Quantidade a adicionar: ")
    if qtd <= 0:
        print(f"{MARGEM}Quantidade deve ser maior que zero.")
        pausar()
        return

    insumo["quantidade"] += qtd
    atualizar_quantidade_db(insumo["id"], insumo["quantidade"])
    salvar_dados(tabela)
    gravar_log("ENTRADA", f"ID={insumo['id']}|{insumo['nome']}|+{qtd:.2f}|estoque={insumo['quantidade']:.2f}")
    print(f"\n{MARGEM}Entrada registrada! Novo estoque: {insumo['quantidade']:.2f} {insumo['unidade']}")
    pausar()

def registrar_saida(tabela: list) -> None:
    limpar_tela()
    linha("=")
    print("  SAÍDA DE ESTOQUE")
    linha("=")

    if not tabela:
        print(f"\n{MARGEM}Nenhum insumo cadastrado.")
        pausar()
        return

    insumo = encontrar_por_id(tabela, ler_inteiro(f"\n{MARGEM}ID do insumo: "))
    if not insumo:
        print(f"{MARGEM}Insumo não encontrado.")
        pausar()
        return

    print(f"\n{MARGEM}{insumo['nome']} — Estoque atual: {insumo['quantidade']:.2f} {insumo['unidade']}")
    qtd = ler_float(f"{MARGEM}Quantidade a retirar: ")

    if qtd <= 0:
        print(f"{MARGEM}Quantidade deve ser maior que zero.")
        pausar()
        return

    if qtd > insumo["quantidade"]:
        print(f"{MARGEM}ERRO: estoque insuficiente! Disponível: {insumo['quantidade']:.2f}")
        pausar()
        return

    insumo["quantidade"] -= qtd
    atualizar_quantidade_db(insumo["id"], insumo["quantidade"])
    salvar_dados(tabela)
    gravar_log("SAIDA", f"ID={insumo['id']}|{insumo['nome']}|-{qtd:.2f}|estoque={insumo['quantidade']:.2f}")
    print(f"\n{MARGEM}Saída registrada! Novo estoque: {insumo['quantidade']:.2f} {insumo['unidade']}")

    status = status_insumo(insumo)
    if status == "CRITICO":
        print(f"\n{MARGEM}[!!!] ALERTA CRITICO: {insumo['nome']} precisa de reposição URGENTE!")
    elif status == "BAIXO":
        print(f"\n{MARGEM}[! ] ALERTA: estoque de {insumo['nome']} está ficando baixo.")
    pausar()

## Funções de análise e recomendações

def calcular_valor_total(tabela: list) -> float:
    return sum(i["quantidade"] * i["preco"] for i in tabela)

def agrupar_por_categoria(tabela: list) -> dict:
    grupos = {}
    for cat in CATEGORIAS:
        itens = [i for i in tabela if i["categoria"] == cat]
        if itens:
            grupos[cat] = {
                "qtd_itens": len(itens),
                "valor_total": sum(i["quantidade"] * i["preco"] for i in itens),
                "estoque_medio": sum(i["quantidade"] for i in itens) / len(itens),
                "preco_medio": sum(i["preco"] for i in itens) / len(itens),
                "itens": itens
            }
    return grupos

def identificar_alertas(tabela: list) -> dict:
    criticos = [i for i in tabela if status_insumo(i) == "CRITICO"]
    baixos = [i for i in tabela if status_insumo(i) == "BAIXO"]
    alto_valor = sorted(tabela, key=lambda x: x["quantidade"] * x["preco"], reverse=True)
    sem_estoque = [i for i in tabela if i["quantidade"] == 0]

    return {
        "criticos": criticos,
        "baixos": baixos,
        "sem_estoque": sem_estoque,
        "top3_valor": alto_valor[:3],
    }

def analisar_movimentacoes() -> dict:
    logs = carregar_log()
    if not logs:
        return None

    entradas = [r for r in logs if r["tipo"] == "ENTRADA"]
    saidas = [r for r in logs if r["tipo"] == "SAIDA"]
    cadastros = [r for r in logs if r["tipo"] == "CADASTRO"]

    frequencia_saida = {}
    for s in saidas:
        partes = s["descricao"].split("|")
        if len(partes) >= 2:
            nome = partes[1]
            frequencia_saida[nome] = frequencia_saida.get(nome, 0) + 1

    mais_consumidos = sorted(frequencia_saida.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_operacoes": len(logs),
        "total_entradas": len(entradas),
        "total_saidas": len(saidas),
        "total_cadastros": len(cadastros),
        "mais_consumidos": mais_consumidos[:5],
        "ultimos_registros": logs[-10:]
    }

def gerar_recomendacoes(tabela: list, analise_mov: dict) -> list:
    recomendacoes = []

    for insumo in tabela:
        status = status_insumo(insumo)
        ideal = insumo.get("limiar_ideal", LIMIAR_ESTOQUE_IDEAL)
        if status in ("CRITICO", "BAIXO"):
            qtd_sugerida = max(0, ideal - insumo["quantidade"])
            custo = qtd_sugerida * insumo["preco"]
            recomendacoes.append({
                "prioridade": "URGENTE" if status == "CRITICO" else "MEDIO",
                "insumo": insumo["nome"],
                "acao": f"Comprar {qtd_sugerida:.0f} {insumo['unidade']}",
                "custo_estimado": custo,
                "fornecedor": insumo["fornecedor"]
            })

    if analise_mov and analise_mov["mais_consumidos"]:
        for nome, freq in analise_mov["mais_consumidos"][:3]:
            insumo = next((i for i in tabela if i["nome"] == nome), None)
            if insumo and status_insumo(insumo) == "ADEQUADO":
                recomendacoes.append({
                    "prioridade": "PREVENTIVO",
                    "insumo": nome,
                    "acao": f"Monitorar — alta frequência de uso ({freq} saídas registradas)",
                    "custo_estimado": 0,
                    "fornecedor": insumo["fornecedor"]
                })

    ordem = {"URGENTE": 0, "MEDIO": 1, "PREVENTIVO": 2}
    recomendacoes.sort(key=lambda r: ordem.get(r["prioridade"], 3))
    return recomendacoes

## Exibi a "Dashboard"

def exibir_dashboard(tabela: list) -> None:
    limpar_tela()
    linha("=")
    print("  DASHBOARD INTELIGENTE — FarmTech Solutions")
    linha("=")

    if not tabela:
        print(f"\n{MARGEM}Cadastre insumos para visualizar o dashboard.")
        pausar()
        return

    valor_total = calcular_valor_total(tabela)
    alertas = identificar_alertas(tabela)
    total_criticos = len(alertas["criticos"])
    total_baixos = len(alertas["baixos"])
    total_adequados = sum(1 for i in tabela if status_insumo(i) == "ADEQUADO")
    total_altos = sum(1 for i in tabela if status_insumo(i) == "ALTO")
    fornecedores = set(i["fornecedor"] for i in tabela)

    print(f"\n{MARGEM}{'VISAO GERAL':^52}")
    linha("-")
    print(f"{MARGEM}Conexão...................: {'Oracle' if conn else 'Local (JSON/TXT)'}")
    print(f"{MARGEM}Total de insumos cadastrados.....: {len(tabela)}")
    print(f"{MARGEM}Fornecedores distintos...........: {len(fornecedores)}")
    print(f"{MARGEM}Valor total em estoque...........: R$ {valor_total:,.2f}")
    print(f"\n{MARGEM}Distribuição de estoque:")
    print(f"{MARGEM}  [!!!] Crítico..: {total_criticos:>3}  "
          f"[! ] Baixo...: {total_baixos:>3}  "
          f"[ + ] Adequado: {total_adequados:>3}  "
          f"[+++] Alto...: {total_altos:>3}")
    saude = ((total_adequados + total_altos) / len(tabela) * 100) if tabela else 0
    print(f"{MARGEM}  Saúde geral do estoque: {saude:.0f}% saudável")

    grupos = agrupar_por_categoria(tabela)
    print(f"\n{MARGEM}{'ANÁLISE POR CATEGORIA':^52}")
    linha("-")
    print(f"{MARGEM}{'Categoria':<15} {'Itens':>6} {'Valor (R$)':>12} {'Estq médio':>11} {'Preço médio':>12}")
    for cat, dados in grupos.items():
        pct = (dados["valor_total"] / valor_total * 100) if valor_total > 0 else 0
        print(
            f"{MARGEM}{cat:<15} {dados['qtd_itens']:>6} "
            f"{dados['valor_total']:>12,.2f} "
            f"{dados['estoque_medio']:>11.1f} "
            f"{dados['preco_medio']:>12.2f}  ({pct:.0f}%)"
        )

    if total_criticos > 0 or total_baixos > 0:
        print(f"\n{MARGEM}{'ALERTAS':^52}")
        linha("-")
        for ins in alertas["criticos"]:
            lc = ins.get('limiar_critico', LIMIAR_ESTOQUE_CRITICO)
            print(f"{MARGEM}[!!!] {ins['nome']}: apenas {ins['quantidade']:.1f} {ins['unidade']} (limiar ≤{lc:.0f}) — REPOSIÇÃO URGENTE")
        for ins in alertas["baixos"]:
            lb = ins.get('limiar_baixo', LIMIAR_ESTOQUE_BAIXO)
            print(f"{MARGEM}[! ] {ins['nome']}: {ins['quantidade']:.1f} {ins['unidade']} (limiar ≤{lb:.0f}) — estoque baixo")

    if alertas["sem_estoque"]:
        print(f"\n{MARGEM}[XXX] SEM ESTOQUE:")
        for ins in alertas["sem_estoque"]:
            print(f"{MARGEM}      - {ins['nome']} (fornecedor: {ins['fornecedor']})")

    print(f"\n{MARGEM}{'MAIOR INVESTIMENTO EM ESTOQUE':^52}")
    linha("-")
    for i, ins in enumerate(alertas["top3_valor"], 1):
        valor = ins["quantidade"] * ins["preco"]
        print(f"{MARGEM}{i}. {ins['nome']}: R$ {valor:,.2f} ({ins['quantidade']:.0f} {ins['unidade']} x R$ {ins['preco']:.2f})")

    analise = analisar_movimentacoes()
    if analise:
        print(f"\n{MARGEM}{'MOVIMENTAÇÕES':^52}")
        linha("-")
        print(f"{MARGEM}Total de operações...: {analise['total_operacoes']}")
        print(f"{MARGEM}Entradas.............: {analise['total_entradas']}")
        print(f"{MARGEM}Saídas...............: {analise['total_saidas']}")
        print(f"{MARGEM}Cadastros............: {analise['total_cadastros']}")

        if analise["ultimos_registros"]:
            ultimo = analise["ultimos_registros"][-1]
            print(f"{MARGEM}Última movimentação..: {ultimo['timestamp']} [{ultimo['tipo']}]")

        if analise["mais_consumidos"]:
            print(f"\n{MARGEM}Insumos mais consumidos (por frequência de saída):")
            for nome, freq in analise["mais_consumidos"]:
                barra = "#" * min(freq, 20)
                print(f"{MARGEM}  {nome:<20} {barra} ({freq}x)")

    recomendacoes = gerar_recomendacoes(tabela, analise)
    if recomendacoes:
        print(f"\n{MARGEM}{'RECOMENDAÇÕES DE COMPRA':^52}")
        linha("-")
        custo_total_rec = 0
        for rec in recomendacoes:
            tag = f"[{rec['prioridade']}]"
            print(f"{MARGEM}{tag:<14} {rec['insumo']}")
            print(f"{MARGEM}{'':14} {rec['acao']}")
            if rec["custo_estimado"] > 0:
                print(f"{MARGEM}{'':14} Custo estimado: R$ {rec['custo_estimado']:,.2f} — Fornecedor: {rec['fornecedor']}")
                custo_total_rec += rec["custo_estimado"]
            print()
        if custo_total_rec > 0:
            print(f"{MARGEM}Investimento estimado para reposição: R$ {custo_total_rec:,.2f}")
    else:
        print(f"\n{MARGEM}Nenhuma recomendação no momento. Estoque saudável!")

    linha("=")
    pausar()

def exibir_historico() -> None:
    limpar_tela()
    linha("=")
    print("  HISTÓRICO DE MOVIMENTAÇÕES")
    linha("=")

    logs = carregar_log()
    if not logs:
        print(f"\n{MARGEM}Nenhuma movimentação registrada.")
        pausar()
        return

    print(f"\n{MARGEM}Últimas 20 operações (mais recentes primeiro):\n")
    ultimos = logs[-20:]
    ultimos.reverse()
    for reg in ultimos:
        print(f"{MARGEM}{reg['timestamp']}  [{reg['tipo']:<12}]  {reg['descricao']}")

    linha("-")
    print(f"{MARGEM}Total de registros no log: {len(logs)}")
    pausar()

## Menu principal e loop

def exibir_menu(tabela: list) -> None:
    linha("=")
    print("  FARMTECH SOLUTIONS — Gestão de Insumos Agrícolas")
    linha("=")

    criticos = sum(1 for i in tabela if status_insumo(i) == "CRITICO")
    if criticos > 0:
        print(f"\n{MARGEM}[!!!] ATENÇÃO: {criticos} insumo(s) com estoque CRÍTICO!")

    print(f"""
{MARGEM}--- Cadastro ---
{MARGEM}1 - Cadastrar insumo
{MARGEM}2 - Listar insumos
{MARGEM}3 - Buscar insumo
{MARGEM}4 - Atualizar insumo
{MARGEM}5 - Excluir insumo

{MARGEM}--- Estoque ---
{MARGEM}6 - Registrar entrada
{MARGEM}7 - Registrar saída

{MARGEM}--- Inteligência ---
{MARGEM}8 - Dashboard inteligente
{MARGEM}9 - Histórico de movimentações

{MARGEM}0 - Sair
""")

def main() -> None:
    oracle_ok = conectar_oracle()
    if oracle_ok:
        criar_tabelas()
    tabela = carregar_dados()
    executando = True

    while executando:
        limpar_tela()
        exibir_menu(tabela)

        escolha = input(f"{MARGEM}Opção: ").strip()
        if not escolha.isdigit():
            print(f"{MARGEM}Digite um número de 0 a 9.")
            pausar()
            continue

        match int(escolha):
            case 1: cadastrar(tabela)
            case 2: listar(tabela)
            case 3: buscar(tabela)
            case 4: atualizar(tabela)
            case 5: excluir(tabela)
            case 6: registrar_entrada(tabela)
            case 7: registrar_saida(tabela)
            case 8: exibir_dashboard(tabela)
            case 9: exibir_historico()
            case 0:
                salvar_dados(tabela)
                desconectar_oracle()
                limpar_tela()
                print(f"\n{MARGEM}Dados salvos. Até a próxima!")
                executando = False
            case _:
                print(f"{MARGEM}Opção inválida.")
                pausar()

if __name__ == "__main__":
    main()