from dataclasses import dataclass, field, asdict

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)
