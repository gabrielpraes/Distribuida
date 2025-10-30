"""
Servidor de Impressão "Burro"
Apenas recebe requisições e imprime, sem participar da exclusão mútua.
"""
import grpc
from concurrent import futures
import time
import sys
import random

import distributed_printing_pb2
import distributed_printing_pb2_grpc


class PrinterServiceImpl(distributed_printing_pb2_grpc.PrintingServiceServicer):
    """
    Implementação do serviço de impressão.
    Este servidor NÃO participa do algoritmo de exclusão mútua.
    """
    
    def __init__(self):
        self.print_count = 0
    
    def SendToPrinter(self, request, context):
        """
        Recebe uma requisição de impressão, imprime a mensagem
        e retorna uma confirmação.
        
        Args:
            request: PrintRequest contendo dados da impressão
            context: Contexto gRPC
            
        Returns:
            PrintResponse: Confirmação da impressão
        """
        self.print_count += 1
        
        # Imprime a mensagem recebida
        print(f"\n{'='*60}")
        print(f"[TS: {request.lamport_timestamp}] CLIENTE {request.client_id}: {request.message_content}")
        print(f"Requisição #{request.request_number}")
        print(f"{'='*60}\n")
        
        # Simula tempo de impressão (2-3 segundos)
        delay = random.uniform(2.0, 3.0)
        print(f"[SERVIDOR] Imprimindo... (aguarde {delay:.1f}s)")
        time.sleep(delay)
        
        print(f"[SERVIDOR] Impressão #{self.print_count} concluída!\n")
        
        # Retorna confirmação
        return distributed_printing_pb2.PrintResponse(
            success=True,
            confirmation_message=f"Impressão #{self.print_count} concluída com sucesso",
            lamport_timestamp=request.lamport_timestamp
        )


def serve():
    """
    Inicia o servidor de impressão na porta 50051
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    distributed_printing_pb2_grpc.add_PrintingServiceServicer_to_server(
        PrinterServiceImpl(), 
        server
    )
    
    port = 50051
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    print(f"{'='*60}")
    print(f"SERVIDOR DE IMPRESSÃO INICIADO")
    print(f"Porta: {port}")
    print(f"Status: Aguardando requisições...")
    print(f"{'='*60}\n")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n[SERVIDOR] Encerrando servidor de impressão...")
        server.stop(0)


if __name__ == '__main__':
    serve()
