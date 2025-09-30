import subprocess
import os
import pyperclip
import sys
import json
from datetime import datetime, timedelta

SETTINGS_FILE = 'settings.json'
DEFAULT_SETTINGS = {
    "show_hashes": True
}

def load_settings():
    """
    Carrega as configurações do arquivo settings.json. Se não existir, cria um.
    """
    if not os.path.exists(SETTINGS_FILE):
        print("Arquivo de configurações não encontrado. Criando um novo com as configurações padrão.")
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        print("Arquivo 'settings.json' criado com sucesso.")
    else:
        print("Configurações lidas com sucesso do arquivo 'settings.json'.")
    
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_commit_message(commit_hash):
    """
    Busca a mensagem completa de um commit a partir do seu hash usando o comando git.
    """
    try:
        command = ['git', 'show', '--no-patch', '--no-notes', '--pretty=format:%B', commit_hash]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Erro ao buscar o commit {commit_hash}: {e.stderr}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("Erro: O comando 'git' não foi encontrado. Certifique-se de que o Git está instalado e no seu PATH.", file=sys.stderr)
        return None

def get_commit_timestamp(commit_hash):
    """
    Busca o timestamp de um commit a partir do seu hash.
    """
    try:
        command = ['git', 'show', '--no-patch', '--no-notes', '--pretty=format:%ad', '--date=format:%Y-%m-%d %H:%M:%S', commit_hash]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Erro ao buscar o timestamp do commit {commit_hash}: {e.stderr}", file=sys.stderr)
        return None
    except FileNotFoundError:
        return None

def format_message(commit_hash, timestamp, message, show_hashes):
    """
    Formata a mensagem de commit com base nas configurações.
    """
    output = ""
    if show_hashes:
        output += f"Commit Hash: {commit_hash}\n"
    output += f"Timestamp: {timestamp}\n"
    output += f"{message}\n"
    output += "-"*50 + "\n"
    return output

def compile_messages(hashes, show_hashes):
    """
    Compila as mensagens, timestamps e hashes em uma única string formatada.
    """
    messages = []
    for h in hashes:
        msg = get_commit_message(h)
        timestamp = get_commit_timestamp(h)
        if msg and timestamp:
            messages.append(format_message(h, timestamp, msg, show_hashes))
    return "".join(messages)

def get_latest_commits(count, show_hashes):
    """
    Busca os hashes e as mensagens dos N últimos commits.
    """
    try:
        # Pega apenas o hash (H)
        command = ['git', 'log', f'-{count}', '--pretty=format:%H']
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        hashes = result.stdout.strip().split('\n')
        
        return compile_messages(hashes, show_hashes)

    except subprocess.CalledProcessError as e:
        print(f"Erro ao obter os últimos commits: {e.stderr}", file=sys.stderr)
        return None

def get_commits_by_date_range(show_hashes):
    """
    Busca commits do dia atual e do dia anterior (ideal para daily reports).
    """
    try:
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        # Formato de data para o Git (YYYY-MM-DD)
        since_date = yesterday.strftime('%Y-%m-%d')
        until_date = (today + timedelta(days=1)).strftime('%Y-%m-%d') # Vai até o final de hoje
        
        print(f"Buscando commits de {yesterday.strftime('%Y-%m-%d')} até {today.strftime('%Y-%m-%d')}...")

        # --since e --until são usados para restringir o período
        command = [
            'git', 'log', 
            f'--since={since_date}', 
            f'--until={until_date}',
            '--pretty=format:%H'
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        hashes = result.stdout.strip().split('\n')
        
        if not hashes or (len(hashes) == 1 and hashes[0] == ''):
            print("Nenhum commit encontrado no período especificado.")
            return None

        return compile_messages(hashes, show_hashes)

    except subprocess.CalledProcessError as e:
        print(f"Erro ao obter commits por data: {e.stderr}", file=sys.stderr)
        return None


def get_messages_from_hashes(show_hashes):
    """
    Solicita hashes de commit, busca as mensagens e as compila em um arquivo de texto.
    """
    hashes = []
    print("Digite os hashes dos commits (um por linha). Pressione Enter em uma linha vazia para finalizar.")

    while True:
        commit_hash = input("Hash do Commit: ").strip()
        if not commit_hash:
            break
        hashes.append(commit_hash)

    if not hashes:
        return None

    print("\nBuscando mensagens de commit...")
    return compile_messages(hashes, show_hashes)

def main():
    """
    Oferece opções para obter mensagens de commit e as salva em um arquivo,
    além de copiar para a área de transferência.
    """
    settings = load_settings()
    show_hashes = settings.get("show_hashes", True)
    print(f"Configuração atual: Mostrar hashes nos resultados = {show_hashes}\n")

    print("Escolha uma opção para obter as mensagens de commit:")
    print("1 - Últimos N commits")
    print("2 - Inserir hashes manualmente")
    print("3 - Commits do Dia Atual e Dia Anterior (Daily Report)")

    choice = input("Opção: ").strip()
    compiled_text = None

    if choice == '1':
        try:
            num_commits = int(input("Quantos commits você quer? (ex: 5): ").strip())
            compiled_text = get_latest_commits(num_commits, show_hashes)
        except ValueError:
            print("Entrada inválida. Por favor, insira um número inteiro.", file=sys.stderr)
            return
    elif choice == '2':
        compiled_text = get_messages_from_hashes(show_hashes)
    elif choice == '3':
        compiled_text = get_commits_by_date_range(show_hashes)
    else:
        print("Opção inválida. Por favor, escolha 1, 2 ou 3.", file=sys.stderr)
        return

    if not compiled_text:
        print("Nenhuma mensagem de commit válida foi encontrada. Encerrando.", file=sys.stderr)
        return

    # Nome do arquivo de saída
    output_filename = "commitsMessages.txt"

    # Salva as mensagens no arquivo
    with open(output_filename, "w", encoding='utf-8') as f:
        f.write(compiled_text)

    # Copia para a área de transferência
    try:
        pyperclip.copy(compiled_text)
        print(f"\nSucesso! As mensagens foram salvas em '{output_filename}' e copiadas para a sua área de transferência.")
    except pyperclip.PyperclipException as e:
        print(f"\nAviso: Não foi possível copiar para a área de transferência. Erro: {e}", file=sys.stderr)
        print(f"As mensagens ainda foram salvas em '{output_filename}'.")

if __name__ == "__main__":
    main()
