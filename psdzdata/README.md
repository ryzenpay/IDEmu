# psdzdata (ponto de montagem de exemplo)

Pasta de exemplo: o `docker-compose.yml` monta `./psdzdata` (este diretório) em
`/psdzdata` no container, somente leitura. Aponte-a para a sua **PSdZData real** de
um dos dois jeitos:

- **`.env`** ao lado do `docker-compose.yml`:
  ```
  IDEMU_PSDZ=/caminho/real/para/psdzdata
  ```
- **`docker-compose.override.yml`** (gitignored) com a montagem direta, no caminho
  que o seu `settings.json` já espera, ex.:
  ```yaml
  services:
    ideemu:
      volumes:
        - "/mnt/z/ISTA+/psdzdata:/mnt/z/ISTA+/psdzdata:ro"
  ```

A pasta montada precisa da estrutura do pacote ISTA+ (`swe/swfl/*.bin.*` e
`mainseries/...`) — é o mesmo conteúdo que a pasta que você escolhe no assistente
da interface. Só os arquivos SWFL são lidos; o container nunca escreve aqui.
