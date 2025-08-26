#!/bin/bash

# Cor para a saída do script
GREEN='\033[0;32m'
NC='\033[0m' # Sem Cor

echo -e "${GREEN}› Checking for staged changes...${NC}"

# 1. Verifica se há arquivos em "stage" (prontos para commit)
# O --quiet faz o comando não imprimir nada, apenas retornar um código de saída.
git diff --cached --quiet
if [ $? -eq 0 ]; then
  echo "No staged changes to commit. Use 'git add <files>' first."
  exit 1
fi

echo -e "${GREEN}› Generating diff...${NC}"
# 2. Cria o arquivo diff.txt com as mudanças em "stage"
git diff --cached > diff.txt

echo -e "${GREEN}› Generating commit message with Gemini AI...${NC}"
# 3. Executa o script Python e captura a mensagem de commit
# O 'tr -d' remove quebras de linha que a IA pode adicionar por engano
COMMIT_MSG=$(python generate_commit.py | tr -d '\n')

# 4. Limpa o arquivo temporário
rm diff.txt

# 5. Verifica se a mensagem foi gerada
if [ -z "$COMMIT_MSG" ]; then
    echo "Error: Could not generate commit message."
    exit 1
fi

echo -e "Generated Message: ${GREEN}${COMMIT_MSG}${NC}"
echo "---"

# 6. Pergunta ao usuário se ele quer usar essa mensagem
read -p "Do you want to commit with this message? (y/n/e to edit) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git commit -m "$COMMIT_MSG"
    echo -e "${GREEN}✓ Commit created successfully!${NC}"
elif [[ $REPLY =~ ^[Ee]$ ]]; then
    # Permite que o usuário edite a mensagem antes de commitar
    git commit -m "$COMMIT_MSG" -e
    echo -e "${GREEN}✓ Commit edited and created successfully!${NC}"
else
    echo "Commit aborted by user."
fi