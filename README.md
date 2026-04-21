# FIAP - Faculdade de Informática e Administração Paulista

<p align="center">
<a href="https://www.fiap.com.br/"><img src="assets/logo-fiap.png" alt="FIAP - Faculdade de Informática e Administração Paulista" border="0" width="40%" height="40%"></a>
</p>

<br>

# Farm Tech

## 👨‍🎓 Integrantes:

- Henrique Sanches Silva - RM570527
- Luís Henrique Laurentino Boschi - 571352
- Kayck Gabriel Evangelista da Silva - 572331
- Patrick Borges de Melo - 574030

## 👩‍🏫 Professores:

### Tutor(a)

- Sabrina Otoni

### Coordenador(a)

- André Godoi Chiovato

## 📜 Descrição

O projeto Farm Tech foi desenvolvido para apoiar a gestão de insumos agrícolas, com foco no setor de insumos do agronegócio. A proposta é resolver uma dor comum do produtor: falta de controle consolidado de estoque, movimentações e prioridade de reposição, o que pode gerar perdas operacionais, desperdício e risco de interrupção na produção.

No contexto do agronegócio, a eficiência da cadeia depende de decisões rápidas e bem informadas. Por isso, a solução oferece um sistema em Python via terminal para cadastro, consulta, atualização e exclusão de insumos, além de registrar entradas e saídas de estoque com histórico em arquivo texto. O projeto inclui recursos de inteligência operacional com classificação de estoque por níveis (crítico, baixo, adequado e alto), alertas automáticos e dashboard com indicadores. Também há recomendações de compra com base no nível de estoque e no histórico de consumo, auxiliando a tomada de decisão de forma prática.

A implementação contempla os conteúdos dos capítulos 3 a 6 da disciplina: subalgoritmos com passagem de parâmetros, uso de estruturas de dados (listas, tuplas e dicionários), manipulação de arquivos texto e JSON, validação de entrada para robustez da aplicação e conexão com banco de dados Oracle para persistência relacional. O sistema opera com dupla persistência: grava no Oracle quando conectado e sempre mantém cópia local em JSON/TXT.

## 🎯 Problema tratado no agronegócio

Controle de insumos agrícolas com prevenção de ruptura de estoque e melhoria da reposição, reduzindo perdas operacionais e apoiando o planejamento de compra.

## ✅ Funcionalidades implementadas

- **CRUD completo** de insumos (cadastro, listagem, busca, atualização e exclusão).
- **Registro de entrada e saída** de estoque com alertas automáticos ao atingir nível crítico ou baixo.
- **Limiares de estoque por produto** — cada insumo possui seus próprios limites (crítico, baixo e ideal), com validação de ordem e valores padrão.
- **Dupla persistência**: Oracle (primário, quando disponível) + JSON/TXT (fallback local, sempre gravado).
- **Histórico de movimentações** com log em arquivo texto e tabela Oracle.
- **Dashboard inteligente** com: visão geral (distribuição de status, saúde do estoque, fornecedores), análise por categoria, alertas com limiares, TOP 3 investimento, frequência de consumo e recomendações de compra priorizadas.
- **Recomendações de compra** com prioridade (urgente/médio/preventivo) e custo estimado.
- **Validação robusta** de entradas: tipos, valores negativos, campos obrigatórios, ordem de limiares.
- **Navegação por etapas** nos wizards de cadastro e atualização (`voltar`/`sair`).

## 📁 Estrutura de pastas

Dentre os arquivos e pastas presentes na raiz do projeto, definem-se:

- <b>assets</b>: arquivos estáticos do repositório, como imagens.
- <b>data</b>: base de dados local gerada/executada pela aplicação (`insumos.json` e `movimentacoes.txt`).
- <b>src</b>: código-fonte principal da aplicação.
- <b>.gitignore</b>: regras de arquivos ignorados no versionamento.
- <b>README.md</b>: documentação principal do projeto.

## � Conteúdos da disciplina aplicados

| Capítulo | Conteúdo                                                           | Aplicação no projeto                                                                                                     |
| -------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| Cap 3    | Subalgoritmos (funções e procedimentos com passagem de parâmetros) | ~40 funções com parâmetros tipados (`cadastrar(tabela)`, `classificar_estoque(quantidade, critico, baixo, ideal)`, etc.) |
| Cap 4    | Estruturas de dados (lista, tupla, dicionário)                     | `tabela: list` de `dict` para insumos, `CATEGORIAS` e `UNIDADES` como tuplas                                             |
| Cap 5    | Manipulação de arquivos (texto e JSON)                             | `insumos.json` (dados principais), `movimentacoes.txt` (log pipe-delimited)                                              |
| Cap 6    | Conexão com banco de dados Oracle                                  | CRUD completo via `oracledb`, DDL automático, fallback para local                                                        |

## 🔧 Como executar o código

### Pré-requisitos

- Python 3.10+ instalado.
- Terminal (PowerShell, CMD ou bash).
- Bibliotecas Python: `oracledb` e `python-dotenv` (instalação no passo 2).
- Arquivo `.env` configurado com as credenciais Oracle (passo 3).

### Passo a passo

1. Clonar o repositório:

```bash
git clone [<url-do-repositorio>](https://github.com/HenriqueSanchesSilva/farm-tech-fase2-cap-6.git)
```

2. Acessar a pasta do projeto:

```bash
cd farm-tech
```

3. Instalar dependências:

```bash
pip install oracledb
pip install dotenv
```

4. Configurar as credenciais do Oracle:

Crie um arquivo `.env` na raiz do projeto:

Abra o `.env` no seu editor e preencha com suas credenciais reais da FIAP:

```env
ORACLE_USER=seu_rm
ORACLE_PASSWORD=sua_senha
ORACLE_DSN=oracle.fiap.com.br:1521/ORCL
```

5. Executar a aplicação:

```bash
python src/main.py
```

6. Utilizar o menu interativo no terminal.

## 🗄 Integração com Oracle

A conexão com banco Oracle está implementada e funcional. O sistema:

- Conecta automaticamente ao iniciar (`oracle.fiap.com.br:1521/ORCL`).
- Cria as tabelas `insumos` (11 colunas) e `movimentacoes` (3 colunas) caso não existam.
- Executa todas as operações CRUD via SQL parametrizado (proteção contra SQL injection).
- Mantém **dupla persistência**: grava no Oracle e em JSON/TXT simultaneamente.
- Se o Oracle estiver indisponível ou o `oracledb` não estiver instalado, o sistema opera normalmente com persistência local.

### Tabelas Oracle

```sql
insumos (id, nome, categoria, unidade, quantidade, preco, fornecedor,
         data_cadastro, limiar_critico, limiar_baixo, limiar_ideal)

movimentacoes (data_hora, tipo, descricao)
```

## 📋 Licença

<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><p xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/"><a property="dct:title" rel="cc:attributionURL" href="https://github.com/agodoi/template">MODELO GIT FIAP</a> por <a rel="cc:attributionURL dct:creator" property="cc:attributionName" href="https://fiap.com.br">FIAP</a> está licenciado sob <a href="http://creativecommons.org/licenses/by/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">Attribution 4.0 International</a>.</p>
