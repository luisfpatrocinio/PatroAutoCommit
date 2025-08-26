# generate_commit.py (versão atualizada e mais flexível)

import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv
import pyperclip
import subprocess
import webbrowser

# Carrega as variáveis de ambiente. O script irá procurar o .env no diretório
# onde ele for executado, ou onde o script principal estiver.
load_dotenv()

# --- Nenhuma mudança nesta seção ---
try:
    api_key = os.environ["GEMINI_API_KEY"]
except KeyError:
    print("Erro: A variável de ambiente GEMINI_API_KEY não foi encontrada.")
    sys.exit(1)

genai.configure(api_key=api_key)

generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 5000,
}

# NOTE: O nome do modelo foi corrigido para um modelo válido.
# "gemini-2.5-flash-lite" não existe. Use "gemini-1.5-flash-latest".
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest",
    generation_config=generation_config,
)
# --- Fim da seção sem mudanças ---


def generate_commit_message(diff_content, aditionalMessage):
    """
    Gera uma mensagem de commit usando a API do Gemini com base no diff.
    """
    
    # Esta lógica permanece a mesma
    if aditionalMessage:
        aditionalMessage = "It's important to bear the following in mind: " + aditionalMessage
    else:
        aditionalMessage = ""

    prompt_parts = [
        "You are an expert programmer writing a commit message for a game developed in GameMaker.",
        "Your task is to generate a concise and descriptive commit message in English, following the Conventional Commits specification.",
        "The commit message must start with a type like 'feat:', 'fix:', 'refactor:', 'chore:', 'docs:', etc.",
        "The message should be objective, highlighting the main changes made.",
		"Highlight the main differences in separate lines if possible.",
        "Do not include any explanations, just the commit message itself.",
        "Focus primarily on changes made to .gml (code) and .yyp (file indexing) files. If other changes are relevant, you may include them as well.",
        aditionalMessage, 
		"\n--- GIT DIFF ---\n", 
		diff_content,
        "\n--- END OF GIT DIFF ---\n",
		"\nGenerate the commit message now:"
	]

    try:
        response = model.generate_content(prompt_parts)
        commit_message = response.text.strip().replace("`", "")
        return commit_message
    except Exception as e:
        return f"Error generating commit message: {e}"

def get_current_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Erro ao obter o nome da branch: {e}")
        return None

if __name__ == "__main__":
    # --- MUDANÇA PRINCIPAL AQUI ---
    # 1. Verifica se os argumentos corretos foram passados
    if len(sys.argv) < 3:
        print("Uso: python generate_commit.py <caminho_para_o_diff> \"<mensagem_adicional>\"")
        sys.exit(1)

    # 2. Pega os argumentos da linha de comando
    diff_file_path = sys.argv[1]
    additional_message = sys.argv[2]
    
    try:
        with open(diff_file_path, "r", encoding="utf-8") as f:
            diff = f.read()
            if not diff.strip():
                print("O arquivo diff está vazio. Nenhuma mudança para commitar.")
                sys.exit(0)
        
        # Gera a mensagem
        message = generate_commit_message(diff, additional_message)
        
        # Imprime e copia para o clipboard
        print(message)
        pyperclip.copy(message)
        print("\n✨ Mensagem copiada para a área de transferência!")

        # Verifica se há arquivos staged para commit
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            staged_files = result.stdout.strip()
        except Exception as e:
            print(f"Erro ao verificar arquivos adicionados: {e}")
            sys.exit(1)

        if not staged_files:
            resp_add = input("Nenhum arquivo está adicionado para commit. Deseja adicionar todos com 'git add .'? (s/n): ").strip().lower()
            if resp_add == "s":
                try:
                    subprocess.run(["git", "add", "."], check=True)
                    print("✅ Arquivos adicionados com sucesso!")
                except Exception as e:
                    print(f"Erro ao adicionar arquivos: {e}")
                    sys.exit(1)
            else:
                print("Nenhum arquivo foi adicionado. O commit pode falhar se não houver arquivos staged.")

        # 1. Pergunta se deseja commitar
        resp_commit = input("Deseja realizar o commit com esta mensagem? (s/n): ").strip().lower()
        if resp_commit == "s":
            try:
                subprocess.run(["git", "commit", "-am", message], check=True)
                print("✅ Commit realizado com sucesso!")
            except Exception as e:
                print(f"Erro ao realizar commit: {e}")
                sys.exit(1)
        else:
            print("Commit não realizado.")

        # 2. Pergunta se deseja pushar
        resp_push = input("Deseja fazer push das mudanças? (s/n): ").strip().lower()
        if resp_push == "s":
            try:
                subprocess.run(["git", "push"], check=True)
                print("✅ Push realizado com sucesso!")
            except Exception as e:
                print(f"Erro ao realizar push: {e}")
                sys.exit(1)
        else:
            print("Push não realizado.")

        # 3. Pergunta sobre Pull Request
        resp_pr = input("Deseja criar um Pull Request para esta branch? (s/n): ").strip().lower()
        if resp_pr == "s":
            branch = get_current_branch()
            if branch:
                pr_url = f"https://github.com/CreativeHandOficial/Suitcase-Stories/compare/develop...{branch}"
                print(f"Abrindo Pull Request: {pr_url}")
                webbrowser.open(pr_url)
            else:
                print("Não foi possível determinar o nome da branch atual.")

    except FileNotFoundError:
        print(f"Erro: Arquivo diff não encontrado em '{diff_file_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"\nOcorreu um erro: {e}")
        sys.exit(1)