# Algoritmo de Ricart-Agrawala - Documentação Detalhada

## Visão Geral

O algoritmo de Ricart-Agrawala é um protocolo distribuído para exclusão mútua que **não requer um coordenador central**. Todos os processos colaboram para decidir quem pode acessar o recurso compartilhado.

### Características Principais

- **Totalmente distribuído**: Nenhum processo é especial
- **Sem deadlock**: Impossível por design
- **Ordenação por timestamps**: Decisões determinísticas
- **Eficiente**: (N-1) mensagens por entrada na seção crítica

## Conceitos Fundamentais

### 1. Estados do Processo

```python
class MutexState(Enum):
    RELEASED = "RELEASED"  # Não precisa do recurso
    WANTED = "WANTED"      # Quer acessar o recurso
    HELD = "HELD"          # Está usando o recurso
```

### 2. Relógio de Lamport

O relógio lógico garante ordenação causal dos eventos:

```python
class LamportClock:
    def tick(self):
        """Incrementa em eventos locais"""
        self._time += 1
        return self._time
    
    def update(self, received_timestamp):
        """Sincroniza com timestamp recebido"""
        self._time = max(self._time, received_timestamp) + 1
        return self._time
```

**Propriedade**: Se evento A aconteceu antes de B, então `timestamp(A) < timestamp(B)`

### 3. Desempate de Requisições

Quando dois processos solicitam ao mesmo tempo:

```python
def tem_prioridade(meu_ts, meu_id, outro_ts, outro_id):
    if meu_ts < outro_ts:
        return True  # Menor timestamp ganha
    elif meu_ts == outro_ts:
        return meu_id < outro_id  # Menor ID como desempate
    else:
        return False
```

## Fluxo do Algoritmo

### Fase 1: REQUISIÇÃO (Estado → WANTED)

```python
def request_critical_section(self):
    # 1. Mudar estado para WANTED
    self.state = MutexState.WANTED
    self.my_request_timestamp = self.clock.tick()
    
    # 2. Enviar requisição para TODOS os outros processos
    for peer in peers:
        send_request(
            client_id=self.id,
            timestamp=self.my_request_timestamp
        )
    
    # 3. Aguardar resposta de TODOS
    wait_for_all_replies()
    
    # 4. Entrar na seção crítica
    self.state = MutexState.HELD
    use_resource()
```

### Fase 2: RESPOSTA (Outro processo requisitando)

```python
def on_request_received(request):
    # Atualizar relógio de Lamport
    self.clock.update(request.timestamp)
    
    # Decidir se responde agora ou adia
    if self.state == MutexState.HELD:
        # Estou usando → adia resposta
        defer_reply(request.client_id)
    
    elif self.state == MutexState.WANTED:
        # Ambos querem → compara timestamps
        if tenho_prioridade(self.my_timestamp, request.timestamp):
            defer_reply(request.client_id)
        else:
            send_reply(request.client_id)
    
    else:  # RELEASED
        # Não quero → responde imediatamente
        send_reply(request.client_id)
```

### Fase 3: LIBERAÇÃO (Estado → RELEASED)

```python
def release_critical_section(self):
    # 1. Mudar estado para RELEASED
    self.state = MutexState.RELEASED
    
    # 2. Responder requisições adiadas
    for deferred_client in deferred_replies:
        send_reply(deferred_client)
    deferred_replies.clear()
    
    # 3. Notificar todos sobre liberação
    for peer in peers:
        send_release_notification(peer)
```

## Exemplo Passo a Passo

### Cenário: 3 Clientes (A, B, C) disputando o recurso

#### Estado Inicial
```
Cliente A: RELEASED, TS=5
Cliente B: RELEASED, TS=3
Cliente C: RELEASED, TS=7
```

#### Passo 1: Cliente A requisita
```
A: estado = WANTED, TS=6 (tick)
A → B: RequestAccess(id=A, ts=6)
A → C: RequestAccess(id=A, ts=6)
```

#### Passo 2: B recebe e responde
```
B: recebe de A (ts=6)
B: atualiza TS = max(3, 6) + 1 = 7
B: estado = RELEASED → responde imediatamente
B → A: AccessResponse(granted=true, ts=7)
```

#### Passo 3: C recebe e responde
```
C: recebe de A (ts=6)
C: atualiza TS = max(7, 6) + 1 = 8
C: estado = RELEASED → responde imediatamente
C → A: AccessResponse(granted=true, ts=8)
```

#### Passo 4: A recebe todas as respostas
```
A: recebeu respostas de B e C
A: estado = HELD
A: usa o recurso (imprime)
```

#### Passo 5: Concorrência - B também quer
```
B: estado = WANTED, TS=8 (tick)
B → A: RequestAccess(id=B, ts=8)
B → C: RequestAccess(id=B, ts=8)

A: recebe de B (ts=8)
A: estado = HELD → adia resposta para B

C: recebe de B (ts=8)
C: atualiza TS = max(8, 8) + 1 = 9
C: estado = RELEASED → responde
C → B: AccessResponse(granted=true, ts=9)
```

#### Passo 6: A libera
```
A: estado = RELEASED, TS=9 (tick)
A: responde requisições adiadas
A → B: AccessResponse(granted=true, ts=9)
A → todos: ReleaseAccess(id=A, ts=9)
```

#### Passo 7: B recebe todas as respostas
```
B: recebeu respostas de A e C
B: estado = HELD
B: usa o recurso
```

## Diagrama de Sequência

```
Tempo →

Cliente A     Cliente B     Cliente C
   |              |              |
   |--REQUEST(6)->|              |
   |--REQUEST(6)---------------->|
   |<-REPLY(7)----|              |
   |<-REPLY(8)-------------------|
   |                             |
   | [HELD - Imprimindo]         |
   |                             |
   |         |--REQUEST(8)------>|
   |<--------|-REQUEST(8)        |
   |         |<-REPLY(9)---------|
   | [Adia resposta para B]      |
   |                             |
   |--RELEASE(9)->|              |
   |--RELEASE(9)---------------->|
   |--REPLY(9)--->|              |
   |         |                   |
   |         | [HELD - Imprimindo]
   |         |                   |
```

## Propriedades de Corretude

### 1. Exclusão Mútua 
**Teorema**: No máximo um processo está em HELD por vez.

**Prova**: 
- Para entrar em HELD, processo precisa de permissão de TODOS
- Se A está HELD, ele não dá permissão para ninguém
- Se B quer entrar, precisa de permissão de A
- A só dá permissão após sair de HELD
- Logo, B só entra depois de A sair

### 2. Ausência de Deadlock 
**Teorema**: Sempre haverá progresso.

**Prova**:
- Requisições são totalmente ordenadas por (timestamp, id)
- Processo com menor timestamp sempre recebe todas as permissões
- Não há ciclo de espera possível

### 3. Ausência de Starvation 
**Teorema**: Todo processo que requisita eventualmente entra.

**Prova**:
- Timestamps são crescentes
- Cada novo pedido tem timestamp maior que os anteriores
- Eventualmente, terá o menor timestamp ativo
- Receberá todas as permissões

### 4. Ordenação Causal 
**Teorema**: Requisições são atendidas na ordem temporal.

**Prova**:
- Relógio de Lamport garante ordem causal
- Desempate por ID é determinístico
- Todos os processos concordam sobre a ordem

## Análise de Complexidade

### Mensagens por Entrada na Seção Crítica
- **Requisição**: N-1 mensagens (broadcast)
- **Resposta**: N-1 mensagens (de volta)
- **Liberação**: N-1 mensagens (notificação)
- **Total**: 3(N-1) mensagens

### Comparação com Outros Algoritmos

| Algoritmo | Mensagens | Coordenador | Falha Única |
|-----------|-----------|-------------|-------------|
| Ricart-Agrawala | 3(N-1) | Não | Tolerante |
| Centralizado | 3 | Sim | Falha total |
| Token Ring | 1 a N | Não | Falha total |
| Lamport | 3(N-1) | Não | Tolerante |

## Casos Especiais

### Caso 1: Timestamps Idênticos
```python
# Cliente 1: requisita com TS=10
# Cliente 2: requisita com TS=10 (coincidência)

if my_ts == other_ts:
    if my_id < other_id:
        # Eu tenho prioridade
        defer_other()
    else:
        # Outro tem prioridade
        grant_immediately()
```

### Caso 2: Processo Falha
```python
# Cliente 3 não responde
try:
    response = stub.RequestAccess(request, timeout=5.0)
except grpc.RpcError:
    # Considera como resposta recebida
    # Sistema continua funcionando
    pending_replies -= 1
```

### Caso 3: Múltiplas Requisições Simultâneas
```python
# A, B, C requisitam ao mesmo tempo
# TS: A=10, B=11, C=12

# Ordem de atendimento:
# 1º: A (menor TS)
# 2º: B (segundo menor TS)
# 3º: C (maior TS)
```

## Implementação Crítica

### Thread Safety
```python
# OBRIGATÓRIO usar locks!
with self.state_lock:
    self.state = MutexState.WANTED
    self.my_request_timestamp = self.clock.tick()

with self.deferred_lock:
    self.deferred_replies.append(client_id)
```

### Sincronização de Respostas
```python
# Usar CountDownLatch ou Event
self.pending_replies = len(peers)
self.reply_event = threading.Event()

# Ao receber resposta
with self.reply_lock:
    self.pending_replies -= 1
    if self.pending_replies == 0:
        self.reply_event.set()

# Aguardar
self.reply_event.wait()
```

### 1. Ricart-Agrawala com Quorum
- Não precisa de todas as N-1 respostas
- Apenas maioria (N/2 + 1)
- Reduz latência

### 2. Ricart-Agrawala com Prioridades
- Processos têm prioridades fixas
- Alta prioridade sempre ganha
- Útil para sistemas em tempo real

### 3. Broadcast Confiável
- Usar ACKs para garantir entrega
- Retransmissão em caso de falha
- Aumenta robustez

