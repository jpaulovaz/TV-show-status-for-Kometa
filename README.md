# Diferenças do Script Original
* Script ajustado para caracteres pt-BR;
* Corrigido o fato do script não salvar os arquivos na pasta do Kometa quando executando em Docker;
* Inseridos alguns scrips para filtros de situações no passado vindo do Plex.
* Script Traduzido para pt-BR.

# 📺 Status dos Seriados para Kometa
Categorias Sonarr:
*  Novos Seriados, que foram incluídos dentro de X dias passados
*  Seriados que um fim de temporada tenha sido adicionados e foi ao ar dentro de X dias passados
*  Seriados com episódios futuros dentro de X dias
*  Seriados que uma nova temoporada ir iniciar dentro de X dias
*  Seriados que uma nova temporada foi ao ar dentro de X dias
*  Seriaods com um episódio final vindo dentro de X dias
*  Seriados que vão Retornar (novos episódio ou temporadas foram confirados, mas não dentro do período informado acima)
*  Seriados Finalizados (Sem novos episódio ou temporadas no futuro)

Categorias Plex:
* Nível Seriado:
  * Overlay para seriados que tenham algum episódio adicionado dentro de X dias passados
  * Overlay para seriados que tenham algum episódio que foi ao ar dentro de X dias passados
  * Overlay para Seriados que tenham alguma temporada adicionada com episódio recente dentro de X dias passados
  * Novo Seriado Adicionado dentro de X dias passados

* Nivel Temporada:
  * Overlay na temporada que tiver algum episódio adicionado dentro de X dias passados
  * Overlay na temporada que tiver algum episódio novo adicionado dentro de X dias passados
  * Overlay na temporada que tiver sido incluída dentro de X dias passados
  * Overlay ba temporada que tiver sido incluída dentro de X dias passados com algum episódio novo (Temporada Atual)

* Nivel Episódio:
    * Overlay no episódio adicionado dentro de X dias passados
    * Overlay no episódio novo adicionado dentro de X dias passados
   
A diferença entre item novo e item adicionado é a idade, pois novo se refere ao que foi ao ar recentemete, e adicionado independe de idade.


  
Exemplo de Overlay (você pode customizar complemente a localização, cor texttos e etc:
![Image](https://github.com/user-attachments/assets/e7c517cc-5164-41d9-8e5e-015577aad36e)

Exemplo de Coleção:</br>
<img width="696" height="403" alt="Image" src="https://github.com/user-attachments/assets/b52c411f-4d73-4386-93c4-38cee8ea2998" />

---

## ✨ Funcionalidades
- 🗓️ **Detecta episódio no futuro, novas temporadas e finais**: Busca no Sonarr pelelos horários dos seriados.
- 🏁 **Rótulos para Episódios finais**: Ussa uma overlay separada para seriados que um final foi adicionado.
-  ▼ **Opicionalmente Filtra os não monitorados**: Pula seriados que não são monitorados no Radarr.
-  🪄 **Customizavel**: Possibilidade de mudar o formado da Data, nome da Coleção, posição da Overlay, texto, ..
-  🌎 **Fuso Horário**:Escolha seu fuso horário indepente de onde o script esteja sendo executado (Docker pode definir direto na variavel TZ=America/Sao_Paulo).
- ℹ️ **Informes**: Lista os seriados com correspondêncoas e os que foram pulados (não monitorados).
- 📝 **Cria arquivo .yml**: Cria um arquivo de coleção e overlay que podem ser usados no Kometa (Arquivos de coleção não são gerados para os filtros feitos pelo Plex)
---

## 🛠️ Instalação

### Escolha seu método de Instalação:

---

### ▶️ Opção 1: Manual (Python)

1. Clone o repositório:
```sh
git clone https://github.com/netplexflix/TV-show-status-for-Kometa.git
cd TV-show-status-for-Kometa
```

> [!TIP]
> Se você não sabe o que isso significa, então simplesmente baixe o script pressionando o botão verde 'Code' acima e em seguida 'Download Zip'. 
> Estraia os arquivos na pasta desejada.

2. Instale as dempendências:
- Certifique de ter [Python](https://www.python.org/downloads/) instalado (`>=3.9`).
- Abra um terminal apontando para o diretório deo scpirt.
> [!TIP]
>Usuário Windows:  
> Vá para a pasta do TSSK (onde TSSK.py está). Clique com botão direito do mouse em um espaço em branco dentro da pasta e selecione  `Abrir no Terminal`.
- Instale as dependências requeridas executando:
```sh
pip install -r requirements.txt
```

---

### ▶️ opção 2: Docker (Recomendado para automatizar)

Se você prefere não instalar o Python e suas dependência manualmente, você pode usar a imagem oficial deo Docker.
1. Certifique que o [Docker](https://docs.docker.com/get-docker/) esteja instalado.
2. Baixe o `docker-compose.yml` fornecido nesse reposítorio(ou copie o exemplo abaixo).
3. Execute o container:
```sh
docker compose up -d
```

O que isso fará:
- Baixa a versão mais recente da imagem `joaopaulofvaz/tssk` no Docker Hub
- Executa o scitpr dentro em um horário definido ( por padrão 2AM)
- Monta seu diretório de configuração e diretório de saída dentro do container

Você pode customizar a definição de horário modificando a variavel `CRON` no arquivo `docker-compose.yml`.

> [!TIP]
> Você pode apontar o TSSK para salver as coleções/overlays direto no diretório deo kometa ajustando os pontos de montagem do docker.
> 
**Exemplo `docker-compose.yml`:**

```yaml
services:
  tssk:
    image: joaopaulofvaz/tssk:testa
    container_name: tssk
    environment:
      - CRON=02 09 * * * # diariamente às 02AM.
      - DOCKER=true # importante para referenciamento
      - PUID=1000
      - PGID=1000
      - TZ=America/Sao_Paulo # Ajuste seu fuso horário
    volumes:
      - /seu/local/config/tssk:/app/config
      - /seu/local/kometa/config:/app/config/kometa
    restart: unless-stopped
    network_mode: bridge
```

---

### 🧩 Continue a configuração

### 1️⃣ Edite seu arquivo de configuração do Kometa

Abre o seu arquivo config.yml do **Kometa**  (normalemente em `Kometa/config/config.yml`, NÃO é o seu arquivo TSSK).  
O diretório depende de onde seus arquivos sejam configurados no seu setup.

O arquivo `yml`criado pelo TSSK que o Kometa usa são armazenados em pastas diferentes dependendo de como você executa seu script:

- **Instalação Manual**: os arquivos são salvos diretamente na pasta `kometa`onde o TSSK está(ex: `TSSK/kometa/`)
- **Instalação Docker**: Os arquivos são salvos dentro de `/config/kometa/tssk/` no container - presumindo que vocêtenha montado a pasta `config` do Kometa no seu container

Certifiquese que seu arquivo de configuração do Kometa use o diretório correto ao fazer referência a esses arquivos.

No seu arquivo de configuração do Kometa, inclua as seguintes linhas abaixo da sua biblioteca de seriados:

```yaml
TV Shows:
  overlay_files:
    - file: /config/tssk/01_TSSK_TV_FINALIZADOS_OVERLAYS.yml
    - file: /config/tssk/02_TSSK_TV_RETORNANDO_OVERLAYS.yml
    - file: /config/tssk/03_TSSK_TV_NOVO_EPISODIO_OVERLAYS.yml
    - file: /config/tssk/04_TSSK_TV_NOVO_RECENTE_EPISODIO_OVERLAYS.yml
    - file: /config/tssk/05_TSSK_TV_NOVO_EPISODIO_TEMPORADA_OVERLAYS.yml
    - file: /config/tssk/06_TSSK_TV_NOVO_SERIADO_OVERLAYS.yml
    - file: /config/tssk/07_TSSK_TV_NOVA_TEMPORADA_INICIADA_OVERLAYS.yml
    - file: /config/tssk/08_TSSK_TV_NOVA_TEMPORADA_OVERLAYS.yml
    - file: /config/tssk/09_TSSK_TV_PROXIMOS_EPISODIOS_OVERLAYS.yml
    - file: /config/tssk/10_TSSK_TV_PROXIMOS_FINAIS_OVERLAYS.yml
    - file: /config/tssk/11_TSSK_TV_FIM_TEMPORADA_OVERLAYS.yml
    - file: /config/tssk/12_TSSK_TV_EPISODIO_FINAL_OVERLAYS.yml
    - file: /config/tssk/13_TSSK_TV_EPISODIO_NA_TEMPORADA_OVERLAYS.yml
    - file: /config/tssk/14_TSSK_TV_NOVO_EPISODIO_NA_TEMPORADA_OVERLAYS.yml
    - file: /config/tssk/15_TSSK_TV_TEMPORADA_ADICIONADA_OVERLAYS.yml
    - file: /config/tssk/16_TSSK_TV_NOVA_TEMPORADA_ADICIONADA_OVERLAYS.yml
    - file: /config/tssk/17_TSSK_TV_EPISODIO_ADICIONADO_OVERLAYS.yml
    - file: /config/tssk/18_TSSK_TV_NOVO_EPISODIO_ADICIONADO_OVERLAYS.yml
  collection_files:
    - file: /config/tssk/TSSK_TV_EPISODIO_FINAL_COLLECTION.yml
    - file: /config/tssk/TSSK_TV_FIM_TEMPORADA_COLLECTION.yml
    - file: /config/tssk/TSSK_TV_FINALIZADOS_COLLECTION.yml
    - file: /config/tssk/TSSK_TV_FINALIZADOS_COLLECTION.yml
    - file: /config/tssk/TSSK_TV_NOVA_TEMPORADA_COLLECTION.yml
    - file: /config/tssk/TSSK_TV_NOVA_TEMPORADA_INICIADA_COLLECTION.yml
    - file: /config/tssk/TSSK_TV_PROXIMOS_EPISODIOS_COLLECTION.yml
    - file: /config/tssk/TSSK_TV_PROXIMOS_FINAIS_COLLECTION.yml
    - file: /config/tssk/TSSK_TV_RETORNANDO_COLLECTION.yml

```

> [!TIP]
> Adicione apenas os arquivos para as catégorias que você quiser ativar. Todas são opcionais e geradas de forma idependente baseado no seru arquivos de configuração.
> Os arquivos de Overlay oferecem melhor aproveitamento se forem aplicados na sequência numêrica de acordo com o numero informado no nome do arquivo.

### 2️⃣ Edite seu arquivos de Configuração
---

## ⚙️ Configuration
Renomeie `config.example.yml` to `config.yml` e edite o que desejar:

- **sonarr_url:** Insira a URL seu Sonarr.
- **sonarr_api_key:** Pode ser localizada nas configurações do Sonarr em Configurações => Geral => Segurança.
- **skip_unmonitored:** Padrão `true` vai pular os seriados se  os episódio/temporada estiver marcada com Não Monitoradas no Sonarr.
- **utc_offset:** Configure o  deslocamento do [Fuso horário UTC](https://en.wikipedia.org/wiki/List_of_UTC_offsets). Ex.: Rio de Janeiro: -3, Amsterdam: +1, Tokyo: +9, etc.

>[!NOTE]
> Algumas pessoas pode ter seu servidor em diferentes fusos horários (Ex. usando uma seedbox), Portanto o script não converte o dia de exibição para o seu timezone local. Ainda assim você pode informar o deslocamento do fuso horario desejado.

</br>

- **Bloco de Coleção:**
  - **collection_name:** Nome da Coleção.
  - **smart_label:** Escolha a opção de Organização (sort). [Mais Informações Aqui](https://metamanager.wiki/en/latest/files/builders/smart/#sort-options)
  - **sort_title:** Organização dos titulos da Coleção.
  - etc
>[!TIP]
>Você pode inserir quantas variaveis do kometa nesse blocoe o arquivo vai adicionalas automaticamento no arquivo .yml gerado.</br>
>`collection_name` é usado para nomear a coleção e será removido do bloco da coleção.
  
- **backdrop block:**
  - **enable:** Se você quer ou não um backdrop(o banner colorido atrás do texto)
  - Mude o tamanho do backdrop,cor e posição. Você pode adicionar qualquer variavel relevante aqui.[Mais informações em](https://kometa.wiki/en/latest/files/overlays/?h=overlay#backdrop-overlay)
    
- **text block:** 
  - **date_format:** O formato de data que será usado na Overlay. Ex: "yyyy-mm-dd", "mm/dd", "dd/mm", etc.
  - **capitalize_dates:** `true` vai deixar a data em caixa alta.
  - **use_text:** Texto que será usado na overlay antes da data. EX: "NOVA TEMPORADA"
  - Mude a cor e posicionamento do texto. Você pode obter as variaveis relevantes em [Mais informações aqui](https://kometa.wiki/en/latest/files/overlays/?h=overlay#text-overlay)


>[!NOTE]
> Esses São os formatos de data que você pode usar:<br/>
> `d`: Dia com 1 digito (1)<br/>
> `dd`: Dia com 2 digitos (01)<br/>
> `ddd`: Dia da Semana Abreviado (SEG)<br/>
> `dddd`: Dia da Semana Completo (Domingo)<br/>
><br/>
> `m`: Mês com 1 digito (1)<br/>
> `mm`: Mês com 2 digitos (01)<br/>
> `mmm`: Mês Abreviado (Jan)<br/>
> `mmmm`: Mês Completo (Janeiro)<br/>
><br/>
> `yy`: Ano com 2 digitos (25)<br/>
> `yyyy`: Ano Completo (2025)
>
>Divisores podem ser `/`, `-` ou um espaço

---
## 🚀 Usage - Running the Script

If you're using the **Docker setup**, the script will run automatically according to the schedule defined by the `CRON` variable in your `docker-compose.yml`.  
You can inspect the container logs to see output and monitor activity:

```sh
docker logs -f tssk
```

If you're using the **manual install**, follow the instructions below to run the script manually.

Open a Terminal in your script directory and launch the script with:
```sh
python TSSK.py
```
The script will list matched and/or skipped shows and create the .yml files. <br/>
The previous configuration will be erased so Kometa will automatically remove overlays for shows that no longer match the criteria.

> [!TIP]
> Windows users can create a batch file to quickly launch the script.<br/>
> Type `"[path to your python.exe]" "[path to the script]" -r pause"` into a text editor
>
> For example:
> ```
>"C:\Users\User1\AppData\Local\Programs\Python\Python311\python.exe" "P:\TSSK\TSSK.py" -r
>pause
> ```
> Save as a .bat file. You can now double click this batch file to directly launch the script.<br/>
> You can also use this batch file to [schedule](https://www.windowscentral.com/how-create-automated-task-using-task-scheduler-windows-10) the script to run.
---


### ⚠️ **Do you Need Help or have Feedback?**
- Join the [Discord](https://discord.gg/VBNUJd7tx3).

---
## ？ FAQ
**Is there a docker container?**<br/>
I made this for my personal use. I don't use docker myself and have no plans atm to learn how to make dockerfiles.<br/>
If anyone wants to help make one, please feel free to create a pull request!
  
---  
### ❤️ Support the Project
If you like this project, please ⭐ star the repository and share it with the community!

<br/>

[!["Buy Me A Coffee"](https://github.com/user-attachments/assets/5c30b977-2d31-4266-830e-b8c993996ce7)](https://www.buymeacoffee.com/neekokeen)
