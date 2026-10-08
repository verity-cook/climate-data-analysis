from src.extract import extract
from src.load import run as load_run

def main() -> None:
    extract()
    load_run()  

if __name__ == "__main__":
    main()