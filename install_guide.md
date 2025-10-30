# Guia de Instalação e Configuração

## 📋 Pré-requisitos

- **Python**: Versão 3.7 ou superior
- **pip**: Gerenciador de pacotes Python
- **Sistema Operacional**: Linux, macOS ou Windows

### Verificar instalação do Python

```bash
python --version
# ou
python3 --version
```

Deve mostrar algo como: `Python 3.8.x` ou superior

### Verificar instalação do pip

```bash
pip --version
# ou
pip3 --version
```

## 🚀 Instalação Passo a Passo

### 1. Criar diretório do projeto

```bash
mkdir distributed-printing-system
cd distributed-printing-system
```

### 2. Criar ambiente virtual (Recomendado)

#### Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

#### Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

Você verá `(venv)` no prompt quando o ambiente estiver ativado.

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

Isso instalará:
- `grpcio` - Framework gRPC
- `grpcio-tools` - Ferramentas de compilação
- `protobuf` - Protocol Buffers

### 4. Compilar arquivo .proto

```bash
chmod +x compile_proto.sh
./compile_proto.sh
```

Ou manualmente:
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. distributed_printing.proto
```

### 5. Verificar instalação

Execute os testes:
```bash
python test_system.py
```

Se todos os testes passarem, a instalação está correta!

## 📁 Estrutura de Arquivos

Após a instalação, seu diretório deve ter:

```
distributed-printing-system/
├── venv/                              # Ambiente virtual (opcional)
├── distributed_printing.proto         # Definição dos serviços
├── distributed_printing_pb2.py        # Gerado automaticamente
├── distributed_printing_pb2_grpc.py   # Gerado automaticamente
├── lamport_clock.py                   # Relógio de Lamport
├── printer_server.py                  # Servidor de impressão
├── printing_client.py                 # Cliente inteligente
├── test_system.py                     # Testes automatizados
├── requirements.txt                   # Dependências
├── compile_proto.sh                   # Script de compilação
├── run_test.sh                        # Script de testes
├── README.md                          # Documentação principal
├── ALGORITMO.md                       # Explicação do algoritmo
└── INSTALACAO.md                      # Este arquivo
```

## 🔧 Configuração

### Portas Utilizadas

| Componente | Porta Padrão | Configurável? |
|------------|--------------|---------------|
| Servidor de Impressão | 50051 | Não |
| Cliente 1 | 50052 | Sim (--port) |
| Cliente 2 | 50053 | Sim (--port) |
| Cliente 3 | 50054 | Sim (--port) |
| Cliente N | 50051+N | Sim (--port) |

### Firewall

Se estiver executando em máquinas diferentes, certifique-se de que as portas estejam abertas:

#### Linux (ufw):
```bash
sudo ufw allow 50051:50060/tcp
```

#### Linux (iptables):
```bash
sudo iptables -A INPUT -p tcp --dport 50051:50060 -j ACCEPT
```

#### Windows:
```powershell
New-NetFirewallRule -DisplayName "gRPC Printing System" -Direction Inbound -Protocol TCP -LocalPort 50051-50060 -Action Allow
```

### Configuração de Rede

#### Mesmo computador (localhost)
```bash
--clients "2:localhost:50053,3:localhost:50054"
```

#### Computadores diferentes
```bash
--clients "2:192.168.1.100:50053,3:192.168.1.101:50054"
```

## Validação da Instalação

### Teste 1: Servidor de Impressão

```bash
python printer_server.py
```

**Saída esperada:**
```
============================================================
SERVIDOR DE IMPRESSÃO INICIADO
Porta: 50051
Status: Aguardando requisições...
============================================================
```

Se aparecer esta mensagem, o servidor está funcionando! ✅

### Teste 2: Cliente Individual

Em outro terminal:
```bash
python printing_client.py --id 1 --port 50052 --clients "2:localhost:50053"
```

**Saída esperada:**
```
[Cliente 1, TS: 0, Estado: RELEASED] Servidor iniciado na porta 50052
[Cliente 1, TS: 0, Estado: RELEASED] Conectado ao servidor de impressão...
[Cliente 1, TS: 0, Estado: RELEASED] Sistema pronto!
```

### Teste 3: Sistema Completo

Use o script de teste:
```bash
chmod +x run_test.sh
./run_test.sh
```

Escolha opção 3 (Teste completo).

## 🐛 Solução de Problemas

### Erro: "ModuleNotFoundError: No module named 'grpc'"

**Solução:**
```bash
pip install grpcio grpcio-tools
```

### Erro: "ModuleNotFoundError: No module named 'distributed_printing_pb2'"

**Causa:** Arquivo .proto não foi compilado.

**Solução:**
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. distributed_printing.proto
```

### Erro: "Address already in use"

**Causa:** Porta já está sendo usada por outro processo.

**Solução Linux/macOS:**
```bash
# Ver processo usando a porta
lsof -i :50051

# Matar processo
kill -9 <PID>
```

**Solução Windows:**
```powershell
# Ver processo usando a porta
netstat -ano | findstr :50051

# Matar processo
taskkill /PID <PID> /F
```

### Erro: "failed to connect to all addresses"

**Causa:** Servidor não está rodando ou endereço incorreto.

**Soluções:**
1. Verificar se o servidor está rodando
2. Verificar endereço e porta corretos
3. Verificar firewall
4. Testar conexão: `telnet localhost 50051`

### Erro: "Permission denied" ao executar .sh

**Solução:**
```bash
chmod +x compile_proto.sh
chmod +x run_test.sh
```

### Warning: "SyntaxWarning" no Python 3.12+

**Causa:** Mudanças no Python 3.12 com imports.

**Solução:** Use Python 3.7 a 3.11, ou ignore o warning (não afeta funcionamento).

### Clientes não se comunicam

**Checklist:**
- [ ] Todos os clientes foram iniciados?
- [ ] Endereços estão corretos na lista `--clients`?
- [ ] Portas estão corretas?
- [ ] Firewall está bloqueando?
- [ ] Clientes estão na mesma rede?

**Teste de conectividade:**
```bash
# De uma máquina, teste conexão com outra
telnet 192.168.1.100 50052
```

### Sistema trava ou não responde

**Possíveis causas:**
1. Deadlock (não deveria acontecer)
2. Cliente esperando resposta que nunca chega
3. Timeout muito longo

**Solução:**
1. Ctrl+C para encerrar
2. Verificar logs de erros
3. Reduzir timeout em `printing_client.py` (linha com `timeout=5.0`)

## 🧪 Testes de Validação

### Teste A: Relógio de Lamport

```bash
python test_system.py TestLamportClock
```

### Teste B: Lógica de Mutex

```bash
python test_system.py TestMutexLogic
```

### Teste C: Ordenação Causal

```bash
python test_system.py TestCausalOrdering
```

### Teste D: Todos os Testes

```bash
python test_system.py
```

## 📊 Monitoramento

### Logs em Tempo Real

```bash
# Terminal 1 - Servidor
python printer_server.py | tee logs_server.txt

# Terminal 2 - Cliente 1
python printing_client.py --id 1 --port 50052 --clients "..." | tee logs_client1.txt

# Terminal 3 - Monitorar logs
tail -f logs_server.txt
tail -f logs_client1.txt
```

### Métricas Importantes

Observe nos logs:
- ✅ Timestamps sempre crescentes
- ✅ Estados corretos (RELEASED → WANTED → HELD → RELEASED)
- ✅ Ordem de impressão respeitando timestamps
- ✅ Respostas adiadas quando necessário

## 🔄 Atualização

### Atualizar dependências

```bash
pip install --upgrade grpcio grpcio-tools protobuf
```

### Recompilar após mudanças no .proto

```bash
./compile_proto.sh
```

## 🌐 Execução em Máquinas Diferentes

### Máquina 1 (Servidor): 192.168.1.100
```bash
python printer_server.py
```

### Máquina 2 (Cliente 1): 192.168.1.101
```bash
python printing_client.py \
    --id 1 \
    --port 50052 \
    --printer "192.168.1.100:50051" \
    --clients "2:192.168.1.102:50053,3:192.168.1.103:50054"
```

### Máquina 3 (Cliente 2): 192.168.1.102
```bash
python printing_client.py \
    --id 2 \
    --port 50053 \
    --printer "192.168.1.100:50051" \
    --clients "1:192.168.1.101:50052,3:192.168.1.103:50054"
```

### Máquina 4 (Cliente 3): 192.168.1.103
```bash
python printing_client.py \
    --id 3 \
    --port 50054 \
    --printer "192.168.1.100:50051" \
    --clients "1:192.168.1.101:50052,2:192.168.1.102:50053"
```

## 💡 Dicas de Performance

### 1. Ajustar intervalos de requisição

Edite `printing_client.py`, linha:
```python
client.run_automatic_requests(interval_range=(5, 10))
```

Para requisições mais frequentes:
```python
client.run_automatic_requests(interval_range=(2, 5))
```

### 2. Ajustar tempo de impressão

Edite `printer_server.py`, linha:
```python
delay = random.uniform(2.0, 3.0)
```

Para impressão mais rápida:
```python
delay = random.uniform(0.5, 1.0)
```

### 3. Aumentar workers do gRPC

Edite nos arquivos, linha:
```python
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
```

Para mais concorrência:
```python
server = grpc.server(futures.ThreadPoolExecutor(max_workers=50))
```

## 📞 Suporte

### Logs de Debug

Para mais detalhes, adicione no início do `printing_client.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Informações Úteis para Depuração

Ao reportar problemas, inclua:
1. Versão do Python: `python --version`
2. Versão do gRPC: `pip show grpcio`
3. Sistema operacional
4. Comando executado
5. Mensagem de erro completa
6. Logs relevantes

## ✅ Checklist Final

Antes de executar o sistema:

- [ ] Python 3.7+ instalado
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] Arquivo .proto compilado (arquivos `*_pb2.py` existem)
- [ ] Portas disponíveis (50051-50054)
- [ ] Firewall configurado (se necessário)
- [ ] Testes passando (`python test_system.py`)

Se todos os itens estão marcados, seu sistema está pronto para uso! 🎉
