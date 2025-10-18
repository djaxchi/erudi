erudi/
 ├─ .gitignore
 ├─ .env
 ├─ README.md
 ├─ LICENSE
 ├─ docs/
 │   ├─ dev/                    # documentation interne pour les devs
 │   └─ user/                   # documentation utilisateur / end users
 ├─ backend/
 │   ├─ app/
 │   │   ├─ engines/              
 │   │   │   ├─ base_engine.py           
 │   │   │   ├─ unified_engine.py        
 │   │   │   ├─ mlx_engine.py            
 │   │   │   ├─ llama_cpp_engine.py      
 │   │   │   ├─ transformers_engine.py   
 │   │   │   └─ utils_build.py           
 │   │   ├─ utils/                
 │   │   │   ├─ inference_utils.py
 │   │   │   └─ logging_utils.py
 │   │   ├─ data/                 
 │   │   │   ├─ models/             
 │   │   │   ├─ models_cache/       
 │   │   │   └─ db/                 
 │   │   ├─ conversations/
 │   │   │   ├─ controller.py
 │   │   │   ├─ service.py
 │   │   │   ├─ model.py
 │   │   │   └─ schema.py
 │   │   ├─ arena/
 │   │   │   ├─ controller.py
 │   │   │   ├─ service.py
 │   │   │   ├─ model.py
 │   │   │   └─ schema.py
 │   │   ├─ hardware/
 │   │   │   ├─ controller.py
 │   │   │   ├─ service.py
 │   │   │   ├─ model.py
 │   │   │   └─ schema.py
 │   │   ├─ knowledge_base/
 │   │   │   ├─ controller.py
 │   │   │   ├─ service.py
 │   │   │   ├─ model.py
 │   │   │   └─ schema.py
 │   │   ├─ download_llm/
 │   │   │   ├─ controller.py
 │   │   │   ├─ service.py
 │   │   │   ├─ model.py
 │   │   │   └─ schema.py
 │   │   ├─ training/
 │   │   │   ├─ controller.py
 │   │   │   ├─ service.py
 │   │   │   ├─ model.py
 │   │   │   └─ schema.py
 │   │   ├─ tests/
 │   │   │   ├─ test_conversations.py
 │   │   │   ├─ test_arena.py
 │   │   │   ├─ test_hardware.py
 │   │   │   ├─ test_knowledge_base.py
 │   │   │   ├─ test_download_llm.py
 │   │   │   ├─ test_training.py
 │   │   │   └─ test_engines.py
 │   │   ├─ main.py
 │   │   ├─ api.py
 │   │   ├─ exceptions.py
 │   │   ├─ logging.py
 │   │   └─ database.py
 │   ├─ forks/
 │   │   └─ llama_cpp/            
 │   │       ├─ CMakeLists.txt
 │   │       ├─ llama.cpp
 │   │       ├─ llama.h
 │   │       └─ ...                
 │   ├─ run.py
 │   └─ requirements/             
 │       ├─ requirements-base.txt     
 │       ├─ requirements-mac.txt      
 │       ├─ requirements-cuda.txt     
 │       └─ requirements-cpu.txt      
 ├─ frontend/                     
 │   ├─ src/
 │   │   ├─ components/
 │   │   ├─ screens/
 │   │   └─ utils/
 │   ├─ package.json
 │   └─ build_scripts/
 │       ├─ build_frontend.sh
 │       └─ build_full_package.sh   # assemble backend exe + frontend
 └─ packaging/
     ├─ backend/
     │   ├─ pyinstaller_spec/
     │   │   ├─ pyinstaller-mac.spec
     │   │   ├─ pyinstaller-cuda.spec
     │   │   └─ pyinstaller-cpu.spec
     │   └─ build_scripts/
     │       └─ package_backend.sh
     ├─ frontend/
     │   └─ build_scripts/
     │       └─ package_frontend.sh
     └─ full_package/
         └─ assemble_package.sh       # intégration backend exe dans frontend



ajouter dans backend/builds/ ça:
pyinstaller_specs/
│ │ │ ├─ mac.spec
│ │ │ ├─ windows.spec
│ │ │ └─ linux.spec

et ça:
└─ build_helpers.py # scripts helper pour assembler le package dynamique selon OS/backend

et ajouter dans backend/app/utils/ ça:
platform_utils.py # OS detection, data_dir helpers, symlink/fallback


Ne pas oublier de prendre en compte mac-x86 en plus de mac-arm64

## next-steps
=> faire un engine awq pour cuda et benchmark contre bnb (taille disk, tok/sec, memoire, vibe-check qual réponses, cmb de bits possibles en quantiz, facilité, agnosticité)
=> faire un engine llamacpp, cad :
    - Fork et mettre en submodule dans backend/llamacpp/fork/
    - Clean le fork pour alléger
    - écrire script de compilation et compiler dans backend/llamacpp/compil/
    - écrire engine llamacpp en étant os-proof sur les subprocess.run 
=> faire engine routing

Tous les Engine doivent proposer ce format :

X_Engine(BaseEngine):
_instance: Optional[Any] = None
_tokenizer: Optional[Any] = None
_model_id: Optional[int] = None
_last_used: Optional[datetime] = None
_lock = threading.Lock()
_cleanup_task = None
_max_idle_time = 300  # 5 minutes
+ d'autres metadata à étudier

quant_and_save_from_hf_format(cls, local_hf_dir: str, dest_dir: str, quantize: bool, q_bit: str) -> None
_load_model_and_tokenizer(cls, llm_id: str, llm_link: str) -> None
get_model_and_tokenizer(cls, llm_id: str) -> Tuple[Any, Any]
generate_stream(
        cls,
        model: Any,
        tokenizer: Any,
        prompt: list[dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 1.0,
        top_p: float = 0.95,
        repetition_penalty: Optional[float] = None,
        **kwargs
): Yields str
cleanup(cls) -> None
_should_cleanup(cls) -> bool
async _cleanup_monitor(cls) -> None
start_cleanup_task(cls) -> None
stop_cleanup_task(cls) -> None