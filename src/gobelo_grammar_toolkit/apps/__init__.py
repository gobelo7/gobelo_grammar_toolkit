class MorphologicalAnalyzer:
    def __init__(self, loader, hfst_backend=None) -> None:
        self._loader  = loader
        self._backend = hfst_backend if hfst_backend  else None # HFSTBackend | None

        print("HFST backend:", type(self._backend))
        if hfst_backend is None:
            print("[WARN] HFST backend not initialized → using heuristic analyzer")

        try:
            self._build_indexes()
        except GGTError as exc:
            raise MorphAnalysisError(f"Failed to build indexes: {exc}") from exc