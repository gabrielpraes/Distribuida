"""
Cliente "Inteligente" de Impressão Distribuída
Implementa o algoritmo de Ricart-Agrawala para exclusão mútua.
"""
import grpc
from concurrent import futures
import time
import threading
import argparse
import random
import sys
from enum import Enum

import distributed_printing_pb2
import distributed_printing_pb2_grpc
from lamport_clock import LamportClock


class MutexState(Enum):
    """Estados do processo na exclusão mútua"""
    RELEASED = "RELEASED"  # Não está interessado no recurso
    WANTED = "WANTED"      # Quer acessar o recurso
    HELD = "HELD"          # Está usando o recurso


class MutualExclusionServiceImpl(distributed_printing_pb2_grpc.MutualExclusionServiceServicer):
    """
    Implementação do serviço de exclusão mútua (lado servidor do cliente).
    Recebe requisições de outros clientes.
    """
    
    def __init__(self, client):
        self.client = client
    
    def RequestAccess(self, request, context):
        """
        Recebe requisição de acesso de outro cliente.
        Implementa a lógica de Ricart-Agrawala para decidir quando responder.
        
        Args:
            request: AccessRequest de outro cliente
            context: Contexto gRPC
            
        Returns:
            AccessResponse: Resposta concedendo ou não o acesso
        """
        # Atualiza relógio com timestamp recebido
        new_time = self.client.clock.update(request.lamport_timestamp)
        
        client_id = request.client_id
        req_timestamp = request.lamport_timestamp
        req_number = request.request_number
        
        self.client.log(
            f"Recebida requisição do Cliente {client_id} "
            f"(TS: {req_timestamp}, Req: {req_number})"
        )
        
        # Decide se responde imediatamente ou adia
        should_defer = False
        
        with self.client.state_lock:
            current_state = self.client.state
            
            # Se está usando o recurso (HELD), deve adiar
            if current_state == MutexState.HELD:
                should_defer = True
                self.client.log(
                    f"Adiando resposta para Cliente {client_id} "
                    f"(Estado: {current_state.value})"
                )
            
            # Se quer o recurso (WANTED), compara timestamps
            elif current_state == MutexState.WANTED:
                # Desempate: menor timestamp tem prioridade
                # Se timestamps iguais, menor ID tem prioridade
                my_ts = self.client.my_request_timestamp
                my_id = self.client.client_id
                
                if (my_ts < req_timestamp) or (my_ts == req_timestamp and my_id < client_id):
                    should_defer = True
                    self.client.log(
                        f"Adiando resposta para Cliente {client_id} "
                        f"(meu TS: {my_ts} < recebido: {req_timestamp})"
                    )
        
        if should_defer:

            # CORREÇÃO DE SEÇÃO CRÍTICA 
            ## cria um evento de sinal pra essa req especifica
            reply_event = threading.Event()
            
            # Adiciona à fila de respostas adiadas
            with self.client.deferred_lock:
                self.client.deferred_replies.append((client_id, reply_event))

            ## deixar esperando atpe release critical section chamar release event
            reply_event.wait()

            ## "acorda" e responde
            self.client.log(f"Concedendo acesso (atrasado) ao Cliente {client_id}")
            return distributed_printing_pb2.AccessResponse(
                access_granted=True,
                lamport_timestamp=self.client.clock.tick() # Atualiza o relógio no momento do envio
            )
        else:
            # Responde imediatamente
            self.client.log(f"Concedendo acesso ao Cliente {client_id}")
            return distributed_printing_pb2.AccessResponse(
                access_granted=True,
                lamport_timestamp=new_time
            )
    
    def ReleaseAccess(self, request, context):
        """
        Recebe notificação de liberação de recurso de outro cliente.
        
        Args:
            request: AccessRelease de outro cliente
            context: Contexto gRPC
            
        Returns:
            Empty: Resposta vazia
        """
        # Atualiza relógio
        self.client.clock.update(request.lamport_timestamp)
        
        self.client.log(
            f"Cliente {request.client_id} liberou o recurso "
            f"(Req: {request.request_number})"
        )
        
        # Decrementa contador de respostas pendentes
        # with self.client.reply_lock:
        #     if self.client.pending_replies > 0:
        #         self.client.pending_replies -= 1
        #         if self.client.pending_replies == 0:
        #             self.client.reply_event.set()
        
        return distributed_printing_pb2.Empty()


class PrintingClient:
    """
    Cliente inteligente que implementa exclusão mútua distribuída
    e se comunica com o servidor de impressão.
    """
    
    def __init__(self, client_id, port, peer_addresses, printer_address):
        self.client_id = client_id
        self.port = port
        self.peer_addresses = peer_addresses
        self.printer_address = printer_address
        
        # Relógio de Lamport
        self.clock = LamportClock()
        
        # Estado da exclusão mútua
        self.state = MutexState.RELEASED
        self.state_lock = threading.Lock()
        
        # Timestamp da requisição atual
        self.my_request_timestamp = 0
        self.request_number = 0
        
        # Controle de respostas
        self.pending_replies = 0
        self.reply_lock = threading.Lock()
        self.reply_event = threading.Event()
        
        # Fila de respostas adiadas
        self.deferred_replies = []
        self.deferred_lock = threading.Lock()
        
        # Servidor gRPC (este cliente como servidor)
        self.server = None
        
        # Stubs para comunicação
        self.printer_stub = None
        self.peer_stubs = {}
        
        # Flag de execução
        self.running = True
    
    def log(self, message):
        """Imprime mensagem de log com informações do cliente"""
        timestamp = self.clock.get_time()
        state = self.state.value
        print(f"[Cliente {self.client_id}, TS: {timestamp}, Estado: {state}] {message}")
    
    def start_server(self):
        """Inicia o servidor gRPC deste cliente"""
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        
        distributed_printing_pb2_grpc.add_MutualExclusionServiceServicer_to_server(
            MutualExclusionServiceImpl(self),
            self.server
        )
        
        self.server.add_insecure_port(f'[::]:{self.port}')
        self.server.start()
        
        self.log(f"Servidor iniciado na porta {self.port}")
    
    def connect_to_peers(self):
        """Estabelece conexões com outros clientes e servidor de impressão"""
        # Conecta ao servidor de impressão
        channel = grpc.insecure_channel(self.printer_address)
        self.printer_stub = distributed_printing_pb2_grpc.PrintingServiceStub(channel)
        self.log(f"Conectado ao servidor de impressão em {self.printer_address}")
        
        # Conecta aos pares
        for peer_id, peer_address in self.peer_addresses.items():
            channel = grpc.insecure_channel(peer_address)
            self.peer_stubs[peer_id] = distributed_printing_pb2_grpc.MutualExclusionServiceStub(channel)
            self.log(f"Conectado ao Cliente {peer_id} em {peer_address}")
    
    def request_critical_section(self):
        """
        Fase de Requisição: Solicita acesso ao recurso compartilhado
        usando o algoritmo de Ricart-Agrawala.
        """
        # Muda estado para WANTED
        with self.state_lock:
            self.state = MutexState.WANTED
            self.my_request_timestamp = self.clock.tick()
            self.request_number += 1
        
        req_ts = self.my_request_timestamp
        req_num = self.request_number
        
        self.log(f"Requisitando acesso (Req #{req_num})...")
        
        # Prepara para receber respostas
        with self.reply_lock:
            self.pending_replies = len(self.peer_stubs)
            self.reply_event.clear()
        
        # Envia requisições para todos os pares
        for peer_id, stub in self.peer_stubs.items():
            try:
                request = distributed_printing_pb2.AccessRequest(
                    client_id=self.client_id,
                    lamport_timestamp=req_ts,
                    request_number=req_num
                )
                
                # Chamada assíncrona
                def send_request(pid, s, req):
                    try:
                        response = s.RequestAccess(req, timeout=5.0)
                        # Atualiza relógio com resposta
                        self.clock.update(response.lamport_timestamp)
                        
                        # Decrementa contador de respostas pendentes
                        with self.reply_lock:
                            self.pending_replies -= 1
                            if self.pending_replies == 0:
                                self.reply_event.set()
                    except grpc.RpcError as e:
                        self.log(f"Erro ao contatar Cliente {pid}: {e.code()}")
                        # Considera como resposta recebida
                        with self.reply_lock:
                            self.pending_replies -= 1
                            if self.pending_replies == 0:
                                self.reply_event.set()
                
                thread = threading.Thread(
                    target=send_request,
                    args=(peer_id, stub, request)
                )
                thread.start()
                
            except Exception as e:
                self.log(f"Erro ao enviar requisição para Cliente {peer_id}: {e}")
        
        # Aguarda todas as respostas
        self.log(f"Aguardando respostas de {len(self.peer_stubs)} clientes...")
        self.reply_event.wait()
        
        # Todas as respostas recebidas, pode entrar na seção crítica
        with self.state_lock:
            self.state = MutexState.HELD
        
        self.log(f"Acesso concedido! Entrando na seção crítica.")
    
    def release_critical_section(self):
        """
        Fase de Liberação: Libera o recurso e responde requisições adiadas.
        """
        req_num = self.request_number
        
        # Muda estado para RELEASED
        with self.state_lock:
            self.state = MutexState.RELEASED
        
        # Incrementa timestamp
        release_ts = self.clock.tick()
        
        self.log(f"Liberando recurso (Req #{req_num})...")
        
        # Responde requisições adiadas
        with self.deferred_lock:

            ## CORREÇÃO DE SEÇÃO CRÍTICA
            # 'self.deferred_replies' agora contém (peer_id, reply_event)

            for peer_id, reply_event in self.deferred_replies:
                self.log(f"Respondendo requisição adiada do Cliente {peer_id}")

                try:
                    # 1. Dispara o evento
                    reply_event.set()
                    # 2. Isso fará a thread 'RequestAccess' daquele cliente (que estava em 'reply_event.wait()')
                    #    acordar e finalmente retornar a resposta AccessResponse(True)
                except Exception as e:
                    self.log(f"Erro ao disparar evento para Cliente {peer_id}: {e}")
            
            self.deferred_replies.clear()
        
        # Notifica todos os pares sobre liberação
        for peer_id, stub in self.peer_stubs.items():
            try:
                release = distributed_printing_pb2.AccessRelease(
                    client_id=self.client_id,
                    lamport_timestamp=release_ts,
                    request_number=req_num
                )
                stub.ReleaseAccess(release, timeout=5.0)
            except grpc.RpcError as e:
                self.log(f"Erro ao notificar Cliente {peer_id}: {e.code()}")
    
    def print_document(self, message):
        """
        Usa o servidor de impressão para imprimir um documento.
        """
        print_ts = self.clock.tick()
        req_num = self.request_number
        
        self.log(f"Enviando para impressora...")
        
        try:
            request = distributed_printing_pb2.PrintRequest(
                client_id=self.client_id,
                message_content=message,
                lamport_timestamp=print_ts,
                request_number=req_num
            )
            
            response = self.printer_stub.SendToPrinter(request, timeout=10.0)
            
            # Atualiza relógio
            self.clock.update(response.lamport_timestamp)
            
            if response.success:
                self.log(f"Impressão concluída: {response.confirmation_message}")
            else:
                self.log(f"Falha na impressão")
                
        except grpc.RpcError as e:
            self.log(f"Erro ao imprimir: {e.code()}")
    
    def request_to_print(self, message):
        """
        Fluxo completo: solicita acesso, imprime e libera.
        """
        self.request_critical_section()
        self.print_document(message)
        self.release_critical_section()
    
    def run_automatic_requests(self, interval_range=(5, 10)):
        """
        Gera requisições automáticas de impressão em intervalos aleatórios.
        """
        messages = [
            "Relatório Mensal de Vendas",
            "Documento Confidencial - Projeto X",
            "Lista de Tarefas Pendentes",
            "Ata da Reunião Semanal",
            "Proposta Comercial 2025",
            "Análise de Desempenho Q4",
            "Contrato de Prestação de Serviços",
            "Planilha de Custos Operacionais"
        ]
        
        while self.running:
            # Aguarda intervalo aleatório
            delay = random.uniform(interval_range[0], interval_range[1])
            time.sleep(delay)
            
            if not self.running:
                break
            
            # Escolhe mensagem aleatória
            message = random.choice(messages)
            
            # Solicita impressão
            self.request_to_print(message)
    
    def shutdown(self):
        """Encerra o cliente graciosamente"""
        self.log("Encerrando cliente...")
        self.running = False
        
        if self.server:
            self.server.stop(0)


def parse_arguments():
    """Processa argumentos da linha de comando"""
    parser = argparse.ArgumentParser(description='Cliente de Impressão Distribuída')
    
    parser.add_argument(
        '--id',
        type=int,
        required=True,
        help='ID único do cliente'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        required=True,
        help='Porta do servidor gRPC deste cliente'
    )
    
    parser.add_argument(
        '--clients',
        type=str,
        required=True,
        help='Lista de outros clientes no formato "id1:host1:port1,id2:host2:port2,..."'
    )
    
    parser.add_argument(
        '--printer',
        type=str,
        default='localhost:50051',
        help='Endereço do servidor de impressão (padrão: localhost:50051)'
    )
    
    return parser.parse_args()


def main():
    args = parse_arguments()
    
    # Processa lista de clientes pares
    peer_addresses = {}
    if args.clients:
        for peer in args.clients.split(','):
            parts = peer.split(':')
            if len(parts) == 3:
                peer_id = int(parts[0])
                peer_host = parts[1]
                peer_port = parts[2]
                peer_addresses[peer_id] = f'{peer_host}:{peer_port}'
    
    # Cria cliente
    client = PrintingClient(
        client_id=args.id,
        port=args.port,
        peer_addresses=peer_addresses,
        printer_address=args.printer
    )
    
    # Inicia servidor
    client.start_server()
    
    # Aguarda um pouco para garantir que todos os servidores estejam prontos
    time.sleep(2)
    
    # Conecta aos pares
    client.connect_to_peers()
    
    client.log("Sistema pronto! Gerando requisições automáticas...\n")
    
    # Configura shutdown hook
    def signal_handler(signum, frame):
        client.shutdown()
        sys.exit(0)
    
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Inicia geração automática de requisições
    try:
        client.run_automatic_requests()
    except KeyboardInterrupt:
        client.shutdown()


if __name__ == '__main__':
    main()
