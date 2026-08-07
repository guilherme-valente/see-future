# Security Policy

## Versões suportadas

Este projeto é desenvolvido em desenvolvimento contínuo (rolling release). Apenas a versão mais recente disponível no branch `main` (e, consequentemente, em produção) é suportada com correções de segurança. Versões anteriores ou forks não são mantidos.

| Versão            | Suportada          |
| ----------------- | ------------------ |
| `main` (produção)  | :white_check_mark: |
| Versões anteriores | :x:                |

## Reportar uma vulnerabilidade

Se encontraste uma vulnerabilidade de segurança neste projeto, agradecemos que a reportes de forma responsável, **antes de a divulgares publicamente** (ex: issues públicas, redes sociais, etc.).

Podes reportar através de qualquer um dos seguintes canais:

- **Email:** guilherme.ap.valente@gmail.com

### O que incluir no relatório

Para nos ajudares a compreender e corrigir o problema rapidamente, inclui sempre que possível:

- Descrição clara da vulnerabilidade e do seu impacto potencial.
- Passos para reproduzir o problema (proof of concept, se aplicável).
- Versão/commit afetado.
- Qualquer sugestão de mitigação ou correção, se tiveres.

### O que esperar

- **Confirmação de receção:** dentro de 72 horas após o reporte.
- **Avaliação inicial:** dentro de 7 dias, com uma indicação sobre se a vulnerabilidade foi validada e qual a sua severidade.
- **Resolução:** o tempo de correção depende da severidade e complexidade do problema. Vulnerabilidades críticas serão priorizadas.
- Serás mantido informado sobre o progresso e creditado no changelog/advisory (caso o desejes), assim que a correção for publicada.

### Divulgação responsável

Pedimos que não divulgues publicamente a vulnerabilidade até que uma correção esteja disponível e implementada em produção, para proteger os utilizadores da aplicação.

## Boas práticas aplicadas neste projeto

- Segredos e credenciais (chaves de API, tokens) não são incluídos no código-fonte; são geridos através de variáveis de ambiente / `st.secrets` (Streamlit).
- Dependências são revistas periodicamente para identificar vulnerabilidades conhecidas.
- Inputs de utilizadores são validados antes de serem processados.

## Fora de âmbito

Não são consideradas vulnerabilidades de segurança para efeitos deste programa:
- Ataques que exijam acesso físico ao dispositivo do utilizador.
- Vulnerabilidades em dependências de terceiros já reportadas publicamente e sem correção disponível pelo fornecedor.
- Problemas de configuração do ambiente de hospedagem (Streamlit Community Cloud) fora do controlo direto do projeto.

---

Obrigado por ajudares a manter este projeto seguro.
