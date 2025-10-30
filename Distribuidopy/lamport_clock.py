"""
Relógio Lógico de Lamport Thread-Safe
"""
import threading


class LamportClock:
    """
    Implementação thread-safe do Relógio Lógico de Lamport
    usando locks para garantir operações atômicas.
    """
    
    def __init__(self):
        self._time = 0
        self._lock = threading.Lock()
    
    def tick(self):
        """
        Incrementa o relógio local e retorna o novo valor.
        Usado quando um evento local ocorre.
        
        Returns:
            int: Novo valor do timestamp
        """
        with self._lock:
            self._time += 1
            return self._time
    
    def update(self, received_timestamp):
        """
        Atualiza o relógio baseado em um timestamp recebido.
        Implementa a lógica: max(local, received) + 1
        
        Args:
            received_timestamp (int): Timestamp recebido de outro processo
            
        Returns:
            int: Novo valor do timestamp
        """
        with self._lock:
            self._time = max(self._time, received_timestamp) + 1
            return self._time
    
    def get_time(self):
        """
        Retorna o valor atual do relógio sem incrementar.
        
        Returns:
            int: Valor atual do timestamp
        """
        with self._lock:
            return self._time
    
    def __str__(self):
        return f"LamportClock(time={self.get_time()})"
