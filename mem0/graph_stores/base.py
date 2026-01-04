from abc import ABC, abstractmethod

class GraphStoreBase(ABC):
    @abstractmethod
    def add(self, nodes, edges):
        pass
    
    @abstractmethod
    def search(self, query):
        pass
        
    @abstractmethod
    def delete(self, filters):
        pass
