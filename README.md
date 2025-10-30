## Readme

# Como rodar

### Passo 1 - dependências

*Versão do Python: 3.8 até 3.12.x*, superior não roda

```bash
pip install -r requirements_txt.txt
```

### Passo 2 - Compilar arquivo .proto

```bash
chmod +x compile_proto.sh
./compile_proto.sh
```

Ou manualmente:
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. distributed_printing.proto
```




## 📂 Estrutura de Arquivos

```
.
├── distributed_printing.proto       # Definição dos serviços gRPC
├── lamport_clock.py                 # Relógio Lógico de Lamport
├── printer_server.py                # Servidor de impressão
├── printing_client.py               # Cliente com exclusão mútua
├── requirements.txt                 # Dependências Python
├── compile_proto.sh                 # Script de compilação
└── README.md                        # Este arquivo
```

## 🎯 Como Executar

### Passo 1: Iniciar o Servidor de Impressão

Em um terminal:

```bash
python printer_server.py
```

Saída esperada:
```
============================================================
SERVIDOR DE IMPRESSÃO INICIADO
Porta: 50051
Status: Aguardando requisições...
============================================================
```

### Passo 2: Iniciar os Clientes

Abra **3 ou mais terminais** para os clientes.

#### Terminal 1 - Cliente 1:
```bash
python printing_client.py --id 1 --port 50052 --clients "2:localhost:50053,3:localhost:50054"
```

#### Terminal 2 - Cliente 2:
```bash
python printing_client.py --id 2 --port 50053 --clients "1:localhost:50052,3:localhost:50054"
```

#### Terminal 3 - Cliente 3:
```bash
python printing_client.py --id 3 --port 50054 --clients "1:localhost:50052,2:localhost:50053"
```

### Parâmetros

- `--id`: ID único do cliente (inteiro)
- `--port`: Porta do servidor gRPC deste cliente
- `--clients`: Lista de outros clientes no formato `"id:host:port,id:host:port,..."`
- `--printer`: (Opcional) Endereço do servidor de impressão (padrão: `localhost:50051`)

## 🧪 Casos de Teste

### Cenário 1: Funcionamento Básico sem Concorrência

1. Cliente A solicita acesso
2. Cliente A coordena com outros clientes (nenhum está usando)
3. Cliente A recebe permissões de todos
4. Cliente A imprime no servidor
5. Cliente A libera o recurso

**Saída esperada no Cliente A:**
```
[Cliente 1, TS: 5, Estado: WANTED] Requisitando acesso...
[Cliente 1, TS: 5, Estado: WANTED] Aguardando respostas de 2 clientes...
[Cliente 1, TS: 8, Estado: HELD] Acesso concedido! Entrando na seção crítica.
[Cliente 1, TS: 9, Estado: HELD] Enviando para impressora...
[Cliente 1, TS: 12, Estado: HELD] Impressão concluída
[Cliente 1, TS: 13, Estado: RELEASED] Liberando recurso...
```

### Cenário 2: Concorrência

1. Cliente C está imprimindo
2. Cliente A e B solicitam acesso simultaneamente
3. Algoritmo decide ordem baseada em timestamps
4. Após C liberar, cliente com menor timestamp imprime
5. Segundo cliente aguarda e imprime após liberação

**Comportamento observado:**
- Cliente C: Estado HELD
- Cliente A: Requisita (TS: 15)
- Cliente B: Requisita (TS: 16)
- Cliente C adia respostas para A e B
- Cliente C libera → A recebe permissão (menor TS)
- A imprime e libera
- B recebe permissão e imprime

## 🔍 Logs Detalhados

### Servidor de Impressão
```
============================================================
[TS: 15] CLIENTE 1: Relatório Mensal de Vendas
Requisição #3
============================================================

[SERVIDOR] Imprimindo... (aguarde 2.5s)
[SERVIDOR] Impressão #1 concluída!
```

### Cliente
```
[Cliente 1, TS: 5, Estado: WANTED] Requisitando acesso (Req #1)...
[Cliente 1, TS: 5, Estado: WANTED] Aguardando respostas de 2 clientes...
[Cliente 1, TS: 8, Estado: WANTED] Recebida requisição do Cliente 2 (TS: 7)
[Cliente 1, TS: 8, Estado: WANTED] Adiando resposta (meu TS: 5 < recebido: 7)
[Cliente 1, TS: 10, Estado: HELD] Acesso concedido!
[Cliente 1, TS: 11, Estado: HELD] Enviando para impressora...
[Cliente 1, TS: 14, Estado: HELD] Impressão concluída
[Cliente 1, TS: 15, Estado: RELEASED] Liberando recurso...
[Cliente 1, TS: 15, Estado: RELEASED] Respondendo requisição adiada do Cliente 2
```

## 🛡️ Características Implementadas

### ✅ Exclusão Mútua (Ricart-Agrawala)
- Decisão distribuída sem coordenador central
- Desempate por timestamp (menor tem prioridade)
- Desempate secundário por ID (menor ID em caso de empate)
- Fila de requisições adiadas

### ✅ Relógio de Lamport
- Thread-safe (locks para operações atômicas)
- Atualização em eventos locais (`tick()`)
- Sincronização em mensagens recebidas (`update()`)
- Ordenação causal de eventos

### ✅ Comunicação gRPC
- Servidor de impressão (PrintingService)
- Serviço de exclusão mútua (MutualExclusionService)
- Chamadas assíncronas para melhor desempenho
- Tratamento de erros e timeouts

### ✅ Requisições Automáticas
- Geração aleatória de documentos
- Intervalos variáveis entre requisições (5-10s)
- Mensagens realistas de documentos

### ✅ Logs em Tempo Real
- Estado atual do cliente
- Timestamp de Lamport
- Eventos de requisição/concessão/liberação
- Mensagens de debug detalhadas

## 🎓 Algoritmo de Ricart-Agrawala

### Estados
- **RELEASED**: Não está interessado no recurso
- **WANTED**: Deseja acessar o recurso
- **HELD**: Está usando o recurso

### Fases

#### 1. Requisição
```python
estado = WANTED
timestamp = clock.tick()
broadcast RequestAccess(id, timestamp) para todos
aguardar respostas de todos
estado = HELD
```

#### 2. Resposta
```python
se estado == HELD ou (estado == WANTED e meu_ts < recebido_ts):
    adiar resposta
senão:
    responder imediatamente
```

#### 3. Liberação
```python
estado = RELEASED
responder requisições adiadas
broadcast ReleaseAccess(id, timestamp) para todos
```

## 🔧 Tratamento de Erros

- **Timeout em RPCs**: 5-10 segundos
- **Cliente não responde**: Considera resposta recebida
- **Erro de conexão**: Log de erro e continua
- **Shutdown gracioso**: Handler de sinais SIGINT/SIGTERM

## 📊 Verificação de Funcionamento

### Teste 1: Verificar ordem de impressão
```
Cliente 1 (TS: 10) e Cliente 2 (TS: 12) requisitam simultaneamente
→ Cliente 1 deve imprimir primeiro
```

### Teste 2: Verificar adiamento de respostas
```
Cliente 1 está imprimindo (HELD)
Cliente 2 requisita acesso
→ Cliente 1 deve adiar resposta até liberar
```

### Teste 3: Verificar sincronização de timestamps
```
Todos os timestamps devem ser crescentes
Nenhum evento deve ter timestamp menor que eventos anteriores
```

## 🐛 Troubleshooting

### Erro: "Address already in use"
```bash
# Matar processos na porta
lsof -ti:50051 | xargs kill -9
lsof -ti:50052 | xargs kill -9
```

### Erro: "Module not found"
```bash
# Recompilar .proto
./compile_proto.sh
```

### Clientes não se comunicam
- Verificar endereços na lista `--clients`
- Verificar firewall local
- Garantir que todos os clientes foram iniciados

## 📚 Referências

- **Ricart-Agrawala Algorithm**: "An Optimal Algorithm for Mutual Exclusion in Computer Networks" (1981)
- **Lamport Clocks**: "Time, Clocks, and the Ordering of Events in a Distributed System" (1978)
- **gRPC**: https://grpc.io/docs/languages/python/

## 👥 Contribuições

Sistema desenvolvido como trabalho acadêmico de Sistemas Distribuídos.

## 📝 Licença

Livre para uso educacional.
