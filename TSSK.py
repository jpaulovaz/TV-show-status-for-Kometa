import requests
import yaml
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import sys
if sys.version_info >= (3, 7):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
import functools
print = functools.partial(print, flush=True)

# Constants
IS_DOCKER = os.getenv("DOCKER", "false").lower() == "true"
VERSION = "2.0.0"

if IS_DOCKER:
    os.makedirs("/app/config/kometa/tssk", exist_ok=True)
    puid = int(os.getenv("PUID", "1000"))
    pgid = int(os.getenv("PGID", "1000"))
    overlay_path = "/app/config/kometa/tssk/"
    collection_path = "/app/config/kometa/tssk/"
    print(f"{BLUE}DOCKER {IS_DOCKER}")
    print(f"{BLUE}PUID {puid}")
    print(f"{BLUE}PGID {pgid}")


# ANSI color codes
GREEN = '\033[32m'
ORANGE = '\033[33m'
BLUE = '\033[34m'
RED = '\033[31m'
RESET = '\033[0m'
BOLD = '\033[1m'

def check_for_updates():
    print(f"Verificando atualizações para TSSK {VERSION}...")
    
    try:
        response = requests.get(
            "https://api.github.com/repos/jpaulovaz/TV-show-status-for-Kometa/releases/latest",
            timeout=10
        )
        response.raise_for_status()
        
        latest_release = response.json()
        latest_version = latest_release.get("tag_name", "").lstrip("v")
        
        def parse_version(version_str):
            return tuple(map(int, version_str.split('.')))
        
        current_version_tuple = parse_version(VERSION)
        latest_version_tuple = parse_version(latest_version)
        
        if latest_version and latest_version_tuple > current_version_tuple:
            print(f"{ORANGE}Uma versão mais recente do TSSK está disponível: {latest_version}{RESET}")
            print(f"{ORANGE}Download: {latest_release.get('html_url', '')}{RESET}")
            print(f"{ORANGE}Notas da Release: {latest_release.get('body', 'Nenhuma notas de lançamento disponíveis')}{RESET}\n")
        else:
            print(f"{GREEN}Você está executando a versão mais recente do Tssk.{RESET}\n")
    except Exception as e:
        print(f"{ORANGE}Não foi possível verificar se há atualizações: {str(e)}{RESET}\n")

def get_config_section(config, primary_key, fallback_keys=None):
    if fallback_keys is None:
        fallback_keys = []
    
    if primary_key in config:
        return config[primary_key]
    
    for key in fallback_keys:
        if key in config:
            return config[key]
    
    return {}

def load_config(file_path='config/config.yml'):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Arquivo de configuração '{file_path}' não encontrado.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Erro ao analisar o arquivo de configuração YAML: {e}")
        sys.exit(1)

def convert_utc_to_local(utc_date_str, utc_offset):
    if not utc_date_str:
        return None
        
    # Remover 'Z' se estiver presente e analisar o DateTime
    clean_date_str = utc_date_str.replace('Z', '')
    utc_date = datetime.fromisoformat(clean_date_str).replace(tzinfo=timezone.utc)
    
    # Aplique o deslocamento do UTC
    local_date = utc_date + timedelta(hours=utc_offset)
    return local_date

def process_sonarr_url(base_url, api_key):
    base_url = base_url.rstrip('/')
    
    if base_url.startswith('http'):
        protocol_end = base_url.find('://') + 3
        next_slash = base_url.find('/', protocol_end)
        if next_slash != -1:
            base_url = base_url[:next_slash]
    
    api_paths = [
        '/api/v3',
        '/sonarr/api/v3'
    ]
    
    for path in api_paths:
        test_url = f"{base_url}{path}"
        try:
            headers = {"X-Api-Key": api_key}
            response = requests.get(f"{test_url}/health", headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"Conectado com sucesso a Sonarr em: {test_url}")
                return test_url
        except requests.exceptions.RequestException as e:
            print(f"{ORANGE}URL de teste {test_url} - Falha: {str(e)}{RESET}")
            continue
    
    raise ConnectionError(f"{RED}Incapaz de estabelecer conexão com Sonarr. Tentei os seguintes URLs:\n" + 
                        "\n".join([f"- {base_url}{path}" for path in api_paths]) + 
                        f"\nVerifique sua chave de URL e API e verifique se SONARR está ssendo executado.{RESET}")
def get_tmdb_status(tvdb_id, tmdb_api_key):
    """Retrieve the status of a show from TMDB using its TVDB id"""
    if not tmdb_api_key or not tvdb_id:
        return None

    try:
        # First call to find the TMDB id from the TVDB id
        find_url = (
            f"http://api.themoviedb.org/3/find/{tvdb_id}?api_key="
            f"{tmdb_api_key}&external_source=tvdb_id"
        )
        resp = requests.get(find_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        tv_results = data.get("tv_results") or []
        if not tv_results:
            return None
        tmdb_id = tv_results[0].get("id")
        if not tmdb_id:
            return None

        details_url = f"http://api.themoviedb.org/3/tv/{tmdb_id}?api_key={tmdb_api_key}"
        resp = requests.get(details_url, timeout=10)
        resp.raise_for_status()
        info = resp.json()
        return info.get("status")
    except Exception as e:
        print(f"{ORANGE}Failed to fetch TMDB status for {tvdb_id}: {e}{RESET}")
        return None

def get_sonarr_series(sonarr_url, api_key):
    try:
        url = f"{sonarr_url}/series"
        headers = {"X-Api-Key": api_key}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"{RED}Erro se conectando ao SONARR: {str(e)}{RESET}")
        sys.exit(1)

def get_sonarr_episodes(sonarr_url, api_key, series_id):
    try:
        url = f"{sonarr_url}/episode?seriesId={series_id}"
        headers = {"X-Api-Key": api_key}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"{RED}Erro a busca de episódios de Sonarr: {str(e)}{RESET}")
        sys.exit(1)

def find_new_season_shows(sonarr_url, api_key, future_days_new_season, utc_offset=0, skip_unmonitored=False):
    cutoff_date = datetime.now(timezone.utc) + timedelta(days=future_days_new_season)
    now_local = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    matched_shows = []
    skipped_shows = []
    
    all_series = get_sonarr_series(sonarr_url, api_key)
    
    for series in all_series:
        episodes = get_sonarr_episodes(sonarr_url, api_key, series['id'])
        
        future_episodes = []
        for ep in episodes:
            # Pular especiais (temporada 0)
            season_number = ep.get('seasonNumber', 0)
            if season_number == 0:
                continue
                
            air_date_str = ep.get('airDateUtc')
            if not air_date_str:
                continue
            
            air_date = convert_utc_to_local(air_date_str, utc_offset)
            
            # Saltar episódios que já foram baixados -eles devem ser tratados como se tivessem sido exibidos
            if ep.get('hasFile', False):
                continue
                
            if air_date > now_local:
                future_episodes.append((ep, air_date))
        
        future_episodes.sort(key=lambda x: x[1])
        
        if not future_episodes:
            continue
        
        next_future, air_date_next = future_episodes[0]
        
        # Verifique se esta é uma nova temporada iniciando (episódio 1 de qualquer temporada)
        # E verifique se não é um show completamente novo (temporada 1)
        if (
            next_future['seasonNumber'] > 1
            and next_future['episodeNumber'] == 1
            and not next_future['hasFile']
            and air_date_next <= cutoff_date
        ):
            tvdb_id = series.get('tvdbId')
            air_date_str_dd_mm_yyyy = air_date_next.date().strftime("%d/%m/%Y")

            show_dict = {
                'title': series['title'],
                'seasonNumber': next_future['seasonNumber'],
                'airDate': air_date_str_dd_mm_yyyy,
                'tvdbId': tvdb_id
            }
            
            if skip_unmonitored:
                episode_monitored = next_future.get("monitored", True)
                
                season_monitored = True
                for season_info in series.get("seasons", []):
                    if season_info.get("seasonNumber") == next_future['seasonNumber']:
                        season_monitored = season_info.get("monitored", True)
                        break
                
                if not episode_monitored or not season_monitored:
                    skipped_shows.append(show_dict)
                    continue
            
            matched_shows.append(show_dict)
        # Se for um show completamente novo (1ª temporada), adicione -o aos programas ignorados para relatórios
        elif (
            next_future['seasonNumber'] == 1
            and next_future['episodeNumber'] == 1
            and not next_future['hasFile']
            and air_date_next <= cutoff_date
        ):
            tvdb_id = series.get('tvdbId')
            air_date_str_dd_mm_yyyy = air_date_next.date().strftime("%d/%m/%Y")

            show_dict = {
                'title': series['title'],
                'seasonNumber': next_future['seasonNumber'],
                'airDate': air_date_str_dd_mm_yyyy,
                'tvdbId': tvdb_id,
                'reason': "New show (Season 1)"  # Adicione motivo para pular
            }
            
            skipped_shows.append(show_dict)
    
    return matched_shows, skipped_shows

def find_upcoming_regular_episodes(sonarr_url, api_key, future_days_upcoming_episode, utc_offset=0, skip_unmonitored=False):
    """Find shows with upcoming non-premiere, non-finale episodes within the specified days"""
    cutoff_date = datetime.now(timezone.utc) + timedelta(days=future_days_upcoming_episode)
    now_local = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    matched_shows = []
    skipped_shows = []
    
    all_series = get_sonarr_series(sonarr_url, api_key)
    
    for series in all_series:
        episodes = get_sonarr_episodes(sonarr_url, api_key, series['id'])
        
        # Episódios de grupo por temporada
        seasons = defaultdict(list)
        for ep in episodes:
            if ep.get('seasonNumber') > 0:  # Skip Specials
                seasons[ep.get('seasonNumber')].append(ep)
        
        # Para cada temporada, encontre o número do episódio máximo para identificar finais
        season_finales = {}
        for season_num, season_eps in seasons.items():
            if season_eps:
                max_ep = max(ep.get('episodeNumber', 0) for ep in season_eps)
                season_finales[season_num] = max_ep
        
        future_episodes = []
        for ep in episodes:
            # Skip specials (season 0)
            season_number = ep.get('seasonNumber', 0)
            if season_number == 0:
                continue
                
            air_date_str = ep.get('airDateUtc')
            if not air_date_str:
                continue
            
            air_date = convert_utc_to_local(air_date_str, utc_offset)
            
            # Saltar episódios que já foram baixados -eles devem ser tratados como se tivessem sido exibidos
            if ep.get('hasFile', False):
                continue
                
            if air_date > now_local and air_date <= cutoff_date:
                future_episodes.append((ep, air_date))
        
        future_episodes.sort(key=lambda x: x[1])
        
        if not future_episodes:
            continue
        
        next_future, air_date = future_episodes[0]
        season_num = next_future.get('seasonNumber')
        episode_num = next_future.get('episodeNumber')
        
        # Pular temporada estreia (episódio 1 de qualquer temporada)
        if episode_num == 1:
            continue
            
        # Pular as finais da temporada
        is_episode_finale = season_num in season_finales and episode_num == season_finales[season_num]
        if is_episode_finale:
            continue
        
        tvdb_id = series.get('tvdbId')
        air_date_str_dd_mm_yyyy = air_date.date().strftime("%d/%m/%Y")

        show_dict = {
            'title': series['title'],
            'seasonNumber': season_num,
            'episodeNumber': episode_num,
            'airDate': air_date_str_dd_mm_yyyy,
            'tvdbId': tvdb_id
        }
        
        if skip_unmonitored:
            episode_monitored = next_future.get("monitored", True)
            
            season_monitored = True
            for season_info in series.get("seasons", []):
                if season_info.get("seasonNumber") == season_num:
                    season_monitored = season_info.get("monitored", True)
                    break
            
            if not episode_monitored or not season_monitored:
                skipped_shows.append(show_dict)
                continue
        
        matched_shows.append(show_dict)
    
    return matched_shows, skipped_shows

def find_upcoming_finales(sonarr_url, api_key, future_days_upcoming_finale, utc_offset=0, skip_unmonitored=False):
    """Encontrar shows com as próximas Fim de temporada nos dias especificados"""
    cutoff_date = datetime.now(timezone.utc) + timedelta(days=future_days_upcoming_finale)
    matched_shows = []
    skipped_shows = []
    
    all_series = get_sonarr_series(sonarr_url, api_key)
    
    for series in all_series:
        episodes = get_sonarr_episodes(sonarr_url, api_key, series['id'])
        
        # Agrupar Episódios por Temporada
        seasons = defaultdict(list)
        for ep in episodes:
            if ep.get('seasonNumber') > 0:  # Skip specials
                seasons[ep.get('seasonNumber')].append(ep)
        
        # Para cada temporada, encontre o número do episódio máximo para identificar finais
        season_finales = {}
        for season_num, season_eps in seasons.items():
            if season_eps:
                max_ep = max(ep.get('episodeNumber', 0) for ep in season_eps)
                # Apenas considere um final se não for o episódio 1
                if max_ep > 1:
                    season_finales[season_num] = max_ep
        
        future_episodes = []
        for ep in episodes:
            # Skip specials (season 0)
            season_number = ep.get('seasonNumber', 0)
            if season_number == 0:
                continue
                
            air_date_str = ep.get('airDateUtc')
            if not air_date_str:
                continue
            
            air_date = convert_utc_to_local(air_date_str, utc_offset)
            
            now_local = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
            
            # Skip episódios que já foram baixados -eles serão tratados por Recent_Season_finales
            if ep.get('hasFile', False):
                continue
                
            if air_date > now_local and air_date <= cutoff_date:
                future_episodes.append((ep, air_date))
        
        future_episodes.sort(key=lambda x: x[1])
        
        if not future_episodes:
            continue
        
        next_future, air_date = future_episodes[0]
        season_num = next_future.get('seasonNumber')
        episode_num = next_future.get('episodeNumber')
        
        # Incluem apenas as finais da temporada e garantir que o número do episódio seja maior que 1
        is_episode_finale = season_num in season_finales and episode_num == season_finales[season_num] and episode_num > 1
        if not is_episode_finale:
            continue
        
        tvdb_id = series.get('tvdbId')
        air_date_str_dd_mm_yyyy = air_date.date().strftime("%d/%m/%Y")

        show_dict = {
            'title': series['title'],
            'seasonNumber': season_num,
            'episodeNumber': episode_num,
            'airDate': air_date_str_dd_mm_yyyy,
            'tvdbId': tvdb_id
        }
        
        if skip_unmonitored:
            episode_monitored = next_future.get("monitored", True)
            
            season_monitored = True
            for season_info in series.get("seasons", []):
                if season_info.get("seasonNumber") == season_num:
                    season_monitored = season_info.get("monitored", True)
                    break
            
            if not episode_monitored or not season_monitored:
                skipped_shows.append(show_dict)
                continue
        
        matched_shows.append(show_dict)
    
    return matched_shows, skipped_shows

def find_ended_shows(sonarr_url, api_key, tmdb_api_key=None):
    """Find shows that have ended and have no upcoming regular episodes (ignoring specials).
    Returns a tuple of (ended_shows, cancelled_shows)."""
    ended_shows = []
    cancelled_shows = []

    all_series = get_sonarr_series(sonarr_url, api_key)

    for series in all_series:
        if series.get("status") == "ended":
            episodes = get_sonarr_episodes(sonarr_url, api_key, series["id"])

            has_future_regular_episodes = False
            for ep in episodes:
                air_date_str = ep.get("airDateUtc")
                season_number = ep.get("seasonNumber", 0)

                if season_number == 0:
                    continue

                if air_date_str:
                    air_date = datetime.fromisoformat(
                        air_date_str.replace("Z", "")
                    ).replace(tzinfo=timezone.utc)
                    if air_date > datetime.now(timezone.utc):
                        has_future_regular_episodes = True
                        break

            if not has_future_regular_episodes:
                tvdb_id = series.get("tvdbId")
                show_dict = {"title": series["title"], "tvdbId": tvdb_id}

                tmdb_status = get_tmdb_status(tvdb_id, tmdb_api_key)
                if tmdb_status and "cancel" in tmdb_status.lower():
                    cancelled_shows.append(show_dict)
                else:
                    ended_shows.append(show_dict)

    return ended_shows, cancelled_shows

def find_returning_shows(sonarr_url, api_key, excluded_tvdb_ids):
    """Encontrar programas com status "continuado" que não estão em outras categorias"""
    matched_shows = []
    
    all_series = get_sonarr_series(sonarr_url, api_key)
    
    for series in all_series:
        # Verifique se o show tem status "continuado"
        if series.get('status') == 'continuing':
            tvdb_id = series.get('tvdbId')
            
            # Pule se este show já estiver em outra categoria
            if tvdb_id in excluded_tvdb_ids:
                continue
                
            show_dict = {
                'title': series['title'],
                'tvdbId': tvdb_id
            }
            
            matched_shows.append(show_dict)
    
    return matched_shows

def find_recent_season_finales(sonarr_url, api_key, recent_days_season_finale, utc_offset=0, skip_unmonitored=False):
    """Encontre shows com status 'continuando' que tinham um ar final da temporada dentro dos dias especificados ou um final futuro que já foi baixado"""
    now_local = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    cutoff_date = now_local - timedelta(days=recent_days_season_finale)
    matched_shows = []
    
    all_series = get_sonarr_series(sonarr_url, api_key)
    
    for series in all_series:
        # Inclua apenas shows contínuos
        if series.get('status') not in ['continuing', 'upcoming']:
            continue
        
        # Pule os programas não monitorados se solicitados
        if skip_unmonitored and not series.get('monitored', True):
            continue
            
        episodes = get_sonarr_episodes(sonarr_url, api_key, series['id'])
        
        # Episódios de grupo por temporada e encontre episódios baixados
        seasons = defaultdict(list)
        downloaded_episodes = defaultdict(list)
        
        for ep in episodes:
            season_number = ep.get('seasonNumber', 0)
            if season_number > 0:  # Skip specials
                seasons[season_number].append(ep)
                if ep.get('hasFile', False):
                    downloaded_episodes[season_number].append(ep)
        
        # Para cada temporada, encontre o número do episódio máximo para identificar finais
        season_finales = {}
        for season_num, season_eps in seasons.items():
            # Considere apenas um final se houver vários episódios na temporada
            if len(season_eps) > 1:
                max_ep = max(ep.get('episodeNumber', 0) for ep in season_eps)
                season_finales[season_num] = max_ep
        
        # Procure as finais da temporada exibida recentemente
        for season_num, max_episode_num in season_finales.items():
            # Pule se nenhum episódio baixado para esta temporada
            if season_num not in downloaded_episodes:
                continue
                
            # Encontre o episódio final
            finale_episode = None
            for ep in downloaded_episodes[season_num]:
                if ep.get('episodeNumber') == max_episode_num:
                    finale_episode = ep
                    break
            
            if not finale_episode:
                continue
                
            # Pule se a temporada não for monitorada e Skip_unmonitored é verdadeiro
            if skip_unmonitored:
                season_monitored = True
                for season_info in series.get("seasons", []):
                    if season_info.get("seasonNumber") == season_num:
                        season_monitored = season_info.get("monitored", True)
                        break
                
                if not season_monitored:
                    continue
                
                # Verifique também se o episódio em si é monitorado
                if not finale_episode.get("monitored", True):
                    continue
            
            air_date_str = finale_episode.get('airDateUtc')
            if not air_date_str:
                continue
                
            air_date = convert_utc_to_local(air_date_str, utc_offset)
            
            # Inclua se:
            # 1. Foi ao ar dentro do período recente, ou
            # 2. Tem uma data futura do ar, mas já foi baixada
            if (air_date <= now_local and air_date >= cutoff_date) or (air_date > now_local and finale_episode.get('hasFile', False)):
                tvdb_id = series.get('tvdbId')
                
                # Se for um episódio futuro que já foi baixado, use a data de hoje em vez
                if air_date > now_local and finale_episode.get('hasFile', False):
                    air_date_str_dd_mm_yyyy = now_local.date().strftime("%d/%m/%Y")
                else:
                    air_date_str_dd_mm_yyyy = air_date.date().strftime("%d/%m/%Y")
                
                show_dict = {
                    'title': series['title'],
                    'seasonNumber': season_num,
                    'episodeNumber': max_episode_num,
                    'airDate': air_date_str_dd_mm_yyyy,
                    'tvdbId': tvdb_id
                }
                
                matched_shows.append(show_dict)
    
    return matched_shows

def find_recent_final_episodes(sonarr_url, api_key, recent_days_final_episode, utc_offset=0, skip_unmonitored=False):
    """Encontre programas com status 'terminou' que tiveram seu episódio final nos dias especificados ou ter um futuro episódio final que já foi baixado"""
    now_local = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    cutoff_date = now_local - timedelta(days=recent_days_final_episode)
    matched_shows = []
    
    all_series = get_sonarr_series(sonarr_url, api_key)
    
    for series in all_series:
        # Inclua apenas shows finais
        if series.get('status') != 'ended':
            continue
            
        # Pule os programas não monitorados se solicitados
        if skip_unmonitored and not series.get('monitored', True):
            continue
            
        episodes = get_sonarr_episodes(sonarr_url, api_key, series['id'])
        
        # Episódios de grupo por temporada e encontre episódios baixados
        seasons = defaultdict(list)
        downloaded_episodes = defaultdict(list)
        
        for ep in episodes:
            season_number = ep.get('seasonNumber', 0)
            if season_number > 0:  # Skip specials
                seasons[season_number].append(ep)
                if ep.get('hasFile', False):
                    downloaded_episodes[season_number].append(ep)
        
        # Pule se nenhum episódio baixado
        if not any(downloaded_episodes.values()):
            continue
            
        # Encontre a temporada mais alta com episódios baixados
        max_season = max(downloaded_episodes.keys()) if downloaded_episodes else 0
        
        # Pule se nenhuma temporada válida encontrada
        if max_season == 0:
            continue
            
        # Encontre o número mais alto de episódio na temporada mais alta
        max_episode_num = max(ep.get('episodeNumber', 0) for ep in downloaded_episodes[max_season])
        
        # Encontre o episódio final
        final_episode = None
        for ep in downloaded_episodes[max_season]:
            if ep.get('episodeNumber') == max_episode_num:
                final_episode = ep
                break
        
        if not final_episode:
            continue
            
        # Pule se a temporada não for monitorada e Skip_unmonitored é True
        if skip_unmonitored:
            season_monitored = True
            for season_info in series.get("seasons", []):
                if season_info.get("seasonNumber") == max_season:
                    season_monitored = season_info.get("monitored", True)
                    break
            
            if not season_monitored:
                continue
            
            # Verifique também se o episódio em si é monitorado
            if not final_episode.get("monitored", True):
                continue
        
        # Verifique se existem episódios futuros que não são baixados
        has_future_undownloaded_episodes = False
        for ep in episodes:
            air_date_str = ep.get('airDateUtc')
            season_number = ep.get('seasonNumber', 0)
            has_file = ep.get('hasFile', False)
            
            if season_number == 0:  # Skip specials
                continue
                
            if air_date_str:
                air_date = convert_utc_to_local(air_date_str, utc_offset)
                if air_date > now_local and not has_file:
                    has_future_undownloaded_episodes = True
                    break
        
        if has_future_undownloaded_episodes:
            continue
            
        air_date_str = final_episode.get('airDateUtc')
        if not air_date_str:
            continue
            
        air_date = convert_utc_to_local(air_date_str, utc_offset)
        
        # Inclua se:
        # 1. Foi ao ar dentro do período recente, ou
        # 2. Tem uma data futura do ar, mas já foi baixada
        if (air_date <= now_local and air_date >= cutoff_date) or (air_date > now_local and final_episode.get('hasFile', False)):
            tvdb_id = series.get('tvdbId')
            
            # Se for um episódio futuro que já foi baixado, use a data de hoje em vez
            if air_date > now_local and final_episode.get('hasFile', False):
                air_date_str_dd_mm_yyyy = now_local.date().strftime("%d/%m/%Y")
            else:
                air_date_str_dd_mm_yyyy = air_date.date().strftime("%d/%m/%Y")
            
            show_dict = {
                'title': series['title'],
                'seasonNumber': max_season,
                'episodeNumber': max_episode_num,
                'airDate': air_date_str_dd_mm_yyyy,
                'tvdbId': tvdb_id
            }
            
            matched_shows.append(show_dict)
    
    return matched_shows

def find_new_season_started(sonarr_url, api_key, recent_days_new_season_started, utc_offset=0, skip_unmonitored=False):
    """Encontre programas onde uma nova temporada (não a primeira temporada) foi baixada dentro dos dias especificados"""
    now_local = datetime.now(timezone.utc) + timedelta(hours=utc_offset)
    cutoff_date = now_local - timedelta(days=recent_days_new_season_started)
    matched_shows = []
    
    all_series = get_sonarr_series(sonarr_url, api_key)
    
    for series in all_series:
        # Pule os programas não monitorados se solicitados
        if skip_unmonitored and not series.get('monitored', True):
            continue
            
        episodes = get_sonarr_episodes(sonarr_url, api_key, series['id'])
        
        # Episódios de grupo por temporada e encontre episódios baixados
        seasons = defaultdict(list)
        downloaded_episodes = defaultdict(list)
        
        for ep in episodes:
            season_number = ep.get('seasonNumber', 0)
            if season_number > 0:  # Skip specials
                seasons[season_number].append(ep)
                if ep.get('hasFile', False):
                    downloaded_episodes[season_number].append(ep)
        
        # Pule se houver apenas uma temporada (novo show)
        if len(seasons) <= 1:
            continue
            
        # Encontre o número mais alto da temporada com episódios baixados
        if not downloaded_episodes:
            continue
            
        max_season_with_downloads = max(downloaded_episodes.keys())
        
        # Skip if it's season 1 (new show)
        if max_season_with_downloads <= 1:
            continue
            
        # Verifique se há temporadas anteriores com downloads (para confirmar que não é um novo show)
        has_previous_season_downloads = any(season < max_season_with_downloads for season in downloaded_episodes.keys())
        if not has_previous_season_downloads:
            continue
        
        # Encontre o primeiro episódio da temporada mais alta que foi baixada
        season_episodes = downloaded_episodes[max_season_with_downloads]
        first_episode = min(season_episodes, key=lambda ep: ep.get('episodeNumber', 999))
        
        # Pule se a temporada não for monitorada e Skip_unmonitored é verdadeiro
        if skip_unmonitored:
            season_monitored = True
            for season_info in series.get("seasons", []):
                if season_info.get("seasonNumber") == max_season_with_downloads:
                    season_monitored = season_info.get("monitored", True)
                    break
            
            if not season_monitored:
                continue
            
            # Verifique também se o episódio em si é monitorado
            if not first_episode.get("monitored", True):
                continue
        
        # Verifique quando este episódio foi baixado (use a data do ar como proxy)
        air_date_str = first_episode.get('airDateUtc')
        if not air_date_str:
            continue
            
        air_date = convert_utc_to_local(air_date_str, utc_offset)
        
        # Inclua se ele foi ao ar dentro do período recente (assumindo que o download aconteceu na data do ar)
        if air_date >= cutoff_date and air_date <= now_local:
            tvdb_id = series.get('tvdbId')
            air_date_str_dd_mm_yyyy = air_date.date().strftime("%d/%m/%Y")
            
            show_dict = {
                'title': series['title'],
                'seasonNumber': max_season_with_downloads,
                'episodeNumber': first_episode.get('episodeNumber'),
                'airDate': air_date_str_dd_mm_yyyy,
                'tvdbId': tvdb_id
            }
            
            matched_shows.append(show_dict)
    
    return matched_shows

def format_date(dd_mm_yyyy, date_format, capitalize=False):
    dt_obj = datetime.strptime(dd_mm_yyyy, "%d/%m/%Y")
    
    format_mapping = {
        'mmm': '%b',    # Nome do mês abreviado
        'mmmm': '%B',   # Nome do mês inteiro
        'mm': '%m',     # Mês de 2 dígitos
        'm': '%-m',     # 1-digit month
        'dddd': '%A',   # Full weekday name
        'ddd': '%a',    # Abbreviated weekday name
        'dd': '%d',     # 2-digit day
        'd': str(dt_obj.day),  # 1-digit day - direct integer conversion
        'yyyy': '%Y',   # 4-digit year
        'yyy': '%Y',    # 3+ digit year
        'yy': '%y',     # 2-digit year
        'y': '%y'       # Year without century
    }
    
    
    # Sort format patterns by length (longest first) to avoid partial matches
    patterns = sorted(format_mapping.keys(), key=len, reverse=True)
    
    # First, replace format patterns with temporary markers
    temp_format = date_format
    replacements = {}
    for i, pattern in enumerate(patterns):
        marker = f"@@{i}@@"
        if pattern in temp_format:
            replacements[marker] = format_mapping[pattern]
            temp_format = temp_format.replace(pattern, marker)
    
    # Now replace the markers with strftime formats
    strftime_format = temp_format
    for marker, replacement in replacements.items():
        strftime_format = strftime_format.replace(marker, replacement)
    
    try:
        result = dt_obj.strftime(strftime_format)
        # Tradução manual do dia da semana
        dias_semana = {
            'Mon': 'SEG',
            'Tue': 'TER',
            'Wed': 'QUA',
            'Thu': 'QUI',
            'Fri': 'SEX',
            'Sat': 'SAB',
            'Sun': 'DOM'
        }
        if '%a' in strftime_format:
            for eng, pt in dias_semana.items():
                result = result.replace(eng, pt)
        if capitalize:
            result = result.upper()
        return result
    except ValueError as e:
        print(f"{RED}Erro: formato de data inválida '{date_format}'. Usando formato padrão.{RESET}")
        return dd_mm_yyyy
    
    try:
        result = dt_obj.strftime(strftime_format)
        if capitalize:
            result = result.upper()
        return result
    except ValueError as e:
        print(f"{RED}Erro: formato de data inválida '{date_format}'. Usando formato padrão.{RESET}")
        return dd_mm_yyyy  # Return original format as fallback

def create_overlay_yaml(output_file, shows, config_sections):
    import yaml
    from copy import deepcopy
    from datetime import datetime

    if not shows:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("#Nenhum seriado com correspondência encontrados")
        return
    
    # Group shows by date if available
    date_to_tvdb_ids = defaultdict(list)
    all_tvdb_ids = set()
    
    # Check if this is a category that doesn't need dates
    no_date_needed = "FIM_TEMPORADA" in output_file or "EPISODIO_FINAL" in output_file or "NOVA_TEMPORADA_INICIADA" in output_file
    
    for s in shows:
        if s.get("tvdbId"):
            all_tvdb_ids.add(s['tvdbId'])
        
        # Only add to date groups if the show has an air date and dates are needed
        if s.get("airDate") and not no_date_needed:
            date_to_tvdb_ids[s['airDate']].append(s.get('tvdbId'))
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    # Extract enable flag and default to True if not specified
    enable_backdrop = backdrop_config.pop("enable", True)

    # Only add backdrop overlay if enabled
    if enable_backdrop and all_tvdb_ids:
        backdrop_config["name"] = "backdrop"
        all_tvdb_ids_str = ", ".join(str(i) for i in sorted(all_tvdb_ids) if i)
        
        overlays_dict["backdrop"] = {
            "overlay": backdrop_config,
            "tvdb_show": all_tvdb_ids_str
        }
    
    # -- Text Blocks --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text and all_tvdb_ids:
        date_format = text_config.pop("date_format", "yyyy-mm-dd")
        use_text = text_config.pop("use_text", "NOVA TEMPORADA")
        capitalize_dates = text_config.pop("capitalize_dates", True)
        
        # For categories that need dates and shows with air dates, create date-specific overlays
        if date_to_tvdb_ids and not no_date_needed:
            for date_str in sorted(date_to_tvdb_ids):
                formatted_date = format_date(date_str, date_format, capitalize_dates)
                sub_overlay_config = deepcopy(text_config)
                sub_overlay_config["name"] = f"text({use_text} {formatted_date})"
                
                tvdb_ids_for_date = sorted(tvdb_id for tvdb_id in date_to_tvdb_ids[date_str] if tvdb_id)
                tvdb_ids_str = ", ".join(str(i) for i in tvdb_ids_for_date)
                
                block_key = f"TSSK_{formatted_date}"
                overlays_dict[block_key] = {
                    "overlay": sub_overlay_config,
                    "tvdb_show": tvdb_ids_str
                }
        # For shows without air dates or categories that don't need dates, create a single overlay
        else:
            sub_overlay_config = deepcopy(text_config)
            sub_overlay_config["name"] = f"text({use_text})"
            
            tvdb_ids_str = ", ".join(str(i) for i in sorted(all_tvdb_ids) if i)
            
            # Extract category name from filename
            if "NOVA_TEMPORADA_INICIADA" in output_file:
                block_key = "TSSK_nova_temporada_iniciada"
            elif "FIM_TEMPORADA" in output_file:
                block_key = "TSSK_final_de_temporada"
            elif "EPISODIO_FINAL" in output_file:
                block_key = "TSSK_episódio_final"
            elif "FINALIZADOS" in output_file:
                block_key = "TSSK_finalizados"
            elif "RETORNANDO" in output_file:
                block_key = "TSSK_retornando"
            elif "CANCELADOS" in output_file:
                block_key = "TSSK_cancelados"
            else:
                block_key = "TSSK_overlay"  # fallback
            
            overlays_dict[block_key] = {
                "overlay": sub_overlay_config,
                "tvdb_show": tvdb_ids_str
            }
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)

#################################PLEX BASED CONFIG#################################
        # ---- Episode Added ----
def create_new_episode_added_overlay_yaml(output_file, config_sections, recent_days):
    "Cria Overlay Para episódios adicionados recentemente, independente da exibição."
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "show",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_added": recent_days }},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "NOVOS EPISÓDIOS")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["episodios_recen_adicionados_nv_seriado"] = {
            "run_definition": "show",
            "builder_level": "show",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_added": recent_days }},
            "overlay": text_config
        }
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)

        # ---- Recent New Episode Added ----
def create_recent_new_episode_added_overlay_yaml(output_file, config_sections, recent_days):
    """Cria Overlay para seriados com informação de episódio novo adicionado"""
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "show",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_air_date": recent_days }},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "EPISÓDIO NOVO")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["episodios_novos_adicionados_nv_seriado"] = {
            "run_definition": "show",
            "builder_level": "show",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_air_date": recent_days }},
            "overlay": text_config
        }
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)

        # ---- Recent New Season Added ----
def create_new_season_added_overlay_yaml(output_file, config_sections, recent_days):
    """Cria Overlay para com nova temporada"""
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "show",
            "plex_search": {
                "type": "season",
                "all":{
                    "added": recent_days,
                    "episode_air_date": int(recent_days)*2}},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "TEMPORADA ATUALIZADA")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["nova_temporada_adicionada_nv_seriado"] = {
            "run_definition": "show",
            "builder_level": "show",
            "plex_search": {
                "type": "season",
                "all":{
                    "added": recent_days,
                    "episode_air_date": int(recent_days)*2}},
            "overlay": text_config
        }
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)

        # ---- New Show ----
def create_new_show_overlay_yaml(output_file, config_sections, recent_days):
    """Create overlay YAML for new shows using Plex filters instead of Sonarr data"""
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "show",
            "plex_search": {
                "type": "show",
                "all":{
                    "added": recent_days}},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "ADICIONADO RECENTEMENTE")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["seriado_adicionado_recentemente_nv_seriado"] = {
            "run_definition": "show",
            "builder_level": "show",
            "plex_search": {
                "type": "show",
                "all":{
                    "added": recent_days}},
            "overlay": text_config
        }
    
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)


        # ---- Season depth Episode Added ----
def create_episode_on_season_overlay_yaml(output_file, config_sections, recent_days):
    """Cria Overlay para temporadas com episódio adicionados."""
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "season",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_added": recent_days}},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "NOVOS EPISÓDIOS")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["episodio_adicionado_temporada_nv_temporada"] = {
            "run_definition": "show",
            "builder_level": "season",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_added": recent_days}},
            "overlay": text_config
        }
    
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)

        # ---- Season depth New Episode ----
def create_new_episode_on_season_overlay_yaml(output_file, config_sections, recent_days):
    """Cria Overlay para temporadas com episódio novo adicionados."""
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "season",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_air_date": recent_days}},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "EPISÓDIO NOVO")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["episodio_novo_temporada_nv_temporada"] = {
            "run_definition": "show",
            "builder_level": "season",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_air_date": recent_days}},
            "overlay": text_config
        }
    
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)

        # ---- Season depth Added Season ----
def create_season_added_overlay_yaml(output_file, config_sections, recent_days):
    """Cria Overlay para temporadas adicionadas Recentemente."""
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "season",
            "plex_search": {
                "type": "season",
                "all":{
                    "added": recent_days}},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "ADICIONADA RECENTEMENTE")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["temporada_adicionada_nv_temporada"] = {
            "run_definition": "show",
            "builder_level": "season",
            "plex_search": {
                "type": "season",
                "all":{
                    "added": recent_days}},
            "overlay": text_config
        }
    
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)

        # ---- Season depth New Added Season ----
def create_new_season_released_overlay_yaml(output_file, config_sections, recent_days):
    """Cria Overlay para Nova temporadas adicionadas."""
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "season",
            "plex_search": {
                "type": "season",
                "all":{
                    "added": recent_days,
                    "episode_air_date": int(recent_days)*2}},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "NOVA TEMPORADA")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["nova_temporada_adicionada_nv_temporada"] = {
            "run_definition": "show",
            "builder_level": "season",
            "plex_search": {
                "type": "season",
                "all":{
                    "added": recent_days,
                    "episode_air_date": int(recent_days)*2}},
            "overlay": text_config
        }
    
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)

        # ---- Episode depth episode added ----
def create_episode_added_overlay_yaml(output_file, config_sections, recent_days):
    """Cria Overlay para Episódios adicionados."""
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "episode",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_added": recent_days}},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "ADICIONADO RECENTEMENTE")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["episodio_adicionado_nv_episodio"] = {
            "run_definition": "show",
            "builder_level": "episode",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_added": recent_days}},
            "overlay": text_config
        }
    
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)

        # ---- Episode depth New episode added ----
def create_new_episode_released_overlay_yaml(output_file, config_sections, recent_days):
    """Cria Overlay para Novos Episódios adicionados."""
    import yaml
    from copy import deepcopy
    
    overlays_dict = {}
    
    # -- Backdrop Block --
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    
    if enable_backdrop:
        backdrop_config["name"] = "backdrop"
        overlays_dict["backdrop"] = {
            "run_definition": "show",
            "builder_level": "episode",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_air_date": recent_days}},
            "overlay": backdrop_config
        }
    
    # -- Text Block --
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    
    if enable_text:
        use_text = text_config.pop("use_text", "EPISÓDIO NOVO")
        text_config.pop("date_format", None)  # Remove if present
        text_config.pop("capitalize_dates", None)  # Remove if present
        
        text_config["name"] = f"text({use_text})"
        
        overlays_dict["novo_episodio_adicionado_nv_episodio"] = {
            "run_definition": "show",
            "builder_level": "episode",
            "plex_search": {
                "type": "episode",
                "all":{
                    "episode_air_date": recent_days}},
            "overlay": text_config
        }
    
    final_output = {"overlays": overlays_dict}
    
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(final_output, f, sort_keys=False, allow_unicode=True)
##############################END PLEX BASED CONFIG##############################


def create_collection_yaml(output_file, shows, config):
    import yaml
    from yaml.representer import SafeRepresenter
    from copy import deepcopy
    from collections import OrderedDict

    # Add representer for OrderedDict
    def represent_ordereddict(dumper, data):
        return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())
    
    yaml.add_representer(OrderedDict, represent_ordereddict, Dumper=yaml.SafeDumper)

    # Determine collection type and get the appropriate config section
    collection_config = {}
    collection_name = ""
    
    if "FIM_TEMPORADA" in output_file:
        config_key = "colecao_fim_temporada"
        summary = f"Seriados com um final de temporada que foi ao ar nós últimos {config.get('recent_days_season_finale', 21)} dias"
    elif "EPISODIO_FINAL" in output_file:
        config_key = "colecao_episodio_final"
        summary = f"Seriados com um episódio final que foi ao ar nós últimos {config.get('recent_days_final_episode', 21)} dias"
    elif "NOVA_TEMPORADA_INICIADA" in output_file:
        config_key = "colecao_nova_temporada_iniciada"
        summary = f"Seriados com uma nova temporada que começou no passado {config.get('recent_days_new_season_started', 14)} days"
    elif "NOVA_TEMPORADA" in output_file:
        config_key = "colecao_nova_temporada"
        summary = f"Seriados com uma nova temporada começando dentro {config.get('future_days_new_season', 31)} days"
    elif "PROXIMOS_EPISODIOS" in output_file:
        config_key = "colecao_proximos_episodios"
        summary = f"Seriados com um próximo episódio dentro {config.get('future_days_upcoming_episode', 31)} days"
    elif "PROXIMOS_FINAIS" in output_file:
        config_key = "colecao_procimos_finais"
        summary = f"Seriados com um final de temporada dentro de {config.get('future_days_upcoming_finale', 31)} days"
    elif "FINALIZADOS" in output_file:
        config_key = "colecao_finalizados"
        summary = "Seriados que já foram Finalizados."
    elif "CANCELADOS" in output_file:
        config_key = "colecao_cancelados"
        summary = "Seriados que foram cancelados."
    elif "RETORNANDO" in output_file:
        config_key = "colecao_seriados_que_retornarao"
        summary = "Seriados que tiveram seu retorno confirmado"
    else:
        # Default fallback
        config_key = None
        collection_name = "colecao_de_seriados"
        summary = "Coleção de Seriados"
    
    # Get the collection configuration if available
    if config_key and config_key in config:
        # Create a deep copy to avoid modifying the original config
        collection_config = deepcopy(config[config_key])
        # Extract the collection name and remove it from the config
        collection_name = collection_config.pop("collection_name", "TV Collection")
    
    class QuotedString(str):
        pass

    def quoted_str_presenter(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')

    yaml.add_representer(QuotedString, quoted_str_presenter, Dumper=yaml.SafeDumper)

    # Handle the case when no shows are found
    if not shows:
        # Create the template for empty collections
        data = {
            "collections": {
                collection_name: {
                    "plex_search": {
                        "all": {
                            "label": collection_name
                        }
                    },
                    "item_label.remove": collection_name,
					"smart_label": "random",
					"build_collection": False
                }
            }
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, Dumper=yaml.SafeDumper, sort_keys=False, allow_unicode=True)
        return
    
    tvdb_ids = [s['tvdbId'] for s in shows if s.get('tvdbId')]
    if not tvdb_ids:
        # Create the template for empty collections
        data = {
            "collections": {
                collection_name: {
                    "plex_search": {
                        "all": {
                            "label": collection_name
                        }
                    },
                    "non_item_remove_label": collection_name,
                    "build_collection": False
                }
            }
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, Dumper=yaml.SafeDumper, sort_keys=False, allow_unicode=True)
        return

    # Convert to comma-separated
    tvdb_ids_str = ", ".join(str(i) for i in sorted(tvdb_ids))

    # Create the collection data structure as a regular dict
    collection_data = {}
    collection_data["summary"] = summary
    
    # Add all remaining parameters from the collection config
    for key, value in collection_config.items():
        # If it's a sort_title, make it a QuotedString
        if key == "sort_title":
            collection_data[key] = QuotedString(value)
        else:
            collection_data[key] = value
    
    # Add sync_mode after the config parameters
    collection_data["sync_mode"] = "sync"
    
    # Add tvdb_show as the last item
    collection_data["tvdb_show"] = tvdb_ids_str

    # Create the final structure with ordered keys
    ordered_collection = OrderedDict()
    
    # Add keys in the desired order
    ordered_collection["summary"] = collection_data["summary"]
    if "sort_title" in collection_data:
        ordered_collection["sort_title"] = collection_data["sort_title"]
    
    # Add all other keys except sync_mode and tvdb_show
    for key, value in collection_data.items():
        if key not in ["summary", "sort_title", "sync_mode", "tvdb_show"]:
            ordered_collection[key] = value
    
    # Add sync_mode and tvdb_show at the end
    ordered_collection["sync_mode"] = collection_data["sync_mode"]
    ordered_collection["tvdb_show"] = collection_data["tvdb_show"]

    data = {
        "collections": {
            collection_name: ordered_collection
        }
    }

    with open(output_file, "w", encoding="utf-8") as f:
        # Use SafeDumper so our custom representer is used
        yaml.dump(data, f, Dumper=yaml.SafeDumper, sort_keys=False, allow_unicode=True)


def main():
    start_time = datetime.now()
    print(f"{BLUE}{'*' * 40}\n{'*' * 15} TSSK {VERSION} {'*' * 15}\n{'*' * 40}{RESET}")
    print(f"\n{BLUE}Inicio do Processo: {start_time.strftime('%H:%M:%S')}\n")
    check_for_updates()

    config = load_config('config/config.yml')
    
    try:
        # Process and validate Sonarr URL
        sonarr_url = process_sonarr_url(config['sonarr_url'], config['sonarr_api_key'])
        sonarr_api_key = config['sonarr_api_key']
        tmdb_api_key = config["tmdb_api_key"]
        
        # Get category-specific future_days values, with fallback to main future_days
        future_days = config.get('future_days', 14)
        future_days_new_season = config.get('future_days_new_season', future_days)
        future_days_upcoming_episode = config.get('future_days_upcoming_episode', future_days)
        future_days_upcoming_finale = config.get('future_days_upcoming_finale', future_days)
        
        # Get recent days values
        recent_days_season_finale = config.get('recent_days_season_finale', 14)
        recent_days_final_episode = config.get('recent_days_final_episode', 14)
        recent_days_new_season_started = config.get('recent_days_new_season_started', 7)
        recent_days_new_show = config.get('recent_days_new_show', 7)
        recent_days_new_episode_added = config.get('recent_days_new_episode_added', 7)
        recent_days_fresh_espisode_added = config.get('recent_days_fresh_espisode_added', 7)
        recent_days_new_season_added = config.get('recent_days_new_season_added', 7)
        recent_days_episode_on_season = config.get('recent_days_episode_on_season', 7)
        recent_days_new_episode_on_season = config.get('recent_days_new_episode_on_season', 7)
        recent_days_season_added = config.get('recent_days_season_added', 7)
        recent_days_new_season_released = config.get('recent_days_new_season_released', 7)
        recent_days_episode_added = config.get('recent_days_episode_added', 7)
        recent_days_new_episode_released = config.get('recent_days_new_episode_released', 7)
        

        utc_offset = float(config.get('utc_offset', 0))
        skip_unmonitored = str(config.get("skip_unmonitored", "false")).lower() == "true"

        # Print chosen values
        print(f"future_days_new_season: {future_days_new_season}")
        print(f"recent_days_new_season_started: {recent_days_new_season_started}")
        print(f"future_days_upcoming_episode: {future_days_upcoming_episode}")
        print(f"future_days_upcoming_finale: {future_days_upcoming_finale}")
        print(f"recent_days_season_finale: {recent_days_season_finale}")
        print(f"recent_days_final_episode: {recent_days_final_episode}")
        print(f"recent_days_new_show: {recent_days_new_show}")
        print(f"recent_days_new_episode_added: {recent_days_new_episode_added}")
        print(f"recent_days_fresh_espisode_added: {recent_days_fresh_espisode_added}")
        print(f"recent_days_new_season_added: {recent_days_new_season_added}")
        print(f"recent_days_episode_on_season: {recent_days_episode_on_season}")
        print(f"recent_days_new_episode_on_season: {recent_days_new_episode_on_season}")
        print(f"recent_days_season_added: {recent_days_season_added}")
        print(f"recent_days_new_season_released: {recent_days_new_season_released}")
        print(f"recent_days_episode_added: {recent_days_episode_added}")
        print(f"recent_days_new_episode_released: {recent_days_new_episode_released}")
        print(f"skip_unmonitored: {skip_unmonitored}\n")
        print(f"UTC offset: {utc_offset} hours\n")

        # Track all tvdbIds to exclude from other categories
        all_excluded_tvdb_ids = set()
        
        # ---- Recent Season Finales ----
        season_finale_shows = find_recent_season_finales(
            sonarr_url, sonarr_api_key, recent_days_season_finale, utc_offset, skip_unmonitored
        )
        
        # Add to excluded IDs
        for show in season_finale_shows:
            if show.get('tvdbId'):
                all_excluded_tvdb_ids.add(show['tvdbId'])
        
        if season_finale_shows:
            print(f"{GREEN}Seriados com um final de temporada que foi ao ar nos últimos {recent_days_season_finale} dias:{RESET}")
            for show in season_finale_shows:
                print(f"- {show['title']} (S{show['seasonNumber']}E{show['episodeNumber']}) foi ao ar em {show['airDate']}")
        
        if IS_DOCKER:

            create_overlay_yaml(overlay_path + "11_TSSK_TV_FIM_TEMPORADA_OVERLAYS.yml", season_finale_shows, 
                               {"backdrop": config.get("backdrop_season_finale", {}),
                                "text": config.get("text_season_finale", {})})

            create_collection_yaml(collection_path + "TSSK_TV_FIM_TEMPORADA_COLLECTION.yml", season_finale_shows, config)
            os.chown(overlay_path + "11_TSSK_TV_FIM_TEMPORADA_OVERLAYS.yml", puid, pgid)
            os.chown(collection_path + "TSSK_TV_FIM_TEMPORADA_COLLECTION.yml", puid, pgid)

        else:
            create_overlay_yaml("11_TSSK_TV_FIM_TEMPORADA_OVERLAYS.yml", season_finale_shows, 
                               {"backdrop": config.get("backdrop_season_finale", {}),
                                "text": config.get("text_season_finale", {})})
            
            create_collection_yaml("TSSK_TV_FIM_TEMPORADA_COLLECTION.yml", season_finale_shows, config)
        
        # ---- Recent Final Episodes ----
        final_episode_shows = find_recent_final_episodes(
            sonarr_url, sonarr_api_key, recent_days_final_episode, utc_offset
        )
        
        # Add to excluded IDs
        for show in final_episode_shows:
            if show.get('tvdbId'):
                all_excluded_tvdb_ids.add(show['tvdbId'])
        
        if final_episode_shows:
            print(f"\n{GREEN}Seriados com um episódio final que foi ao ar nos últimos {recent_days_final_episode} dias:{RESET}")
            for show in final_episode_shows:
                print(f"- {show['title']} (S{show['seasonNumber']}E{show['episodeNumber']}) foi ao ar em {show['airDate']}")
        
        if IS_DOCKER:
            create_overlay_yaml(overlay_path + "12_TSSK_TV_EPISODIO_FINAL_OVERLAYS.yml", final_episode_shows, 
                               {"backdrop": config.get("backdrop_final_episode", {}),
                                "text": config.get("text_final_episode", {})})
        
            create_collection_yaml(collection_path + "TSSK_TV_EPISODIO_FINAL_COLLECTION.yml", final_episode_shows, config)
        
            os.chown(overlay_path + "12_TSSK_TV_EPISODIO_FINAL_OVERLAYS.yml", puid, pgid)
            os.chown(collection_path + "TSSK_TV_EPISODIO_FINAL_COLLECTION.yml", puid, pgid)

        else:
            create_overlay_yaml("12_TSSK_TV_EPISODIO_FINAL_OVERLAYS.yml", final_episode_shows, 
                               {"backdrop": config.get("backdrop_final_episode", {}),
                                "text": config.get("text_final_episode", {})})
        
            create_collection_yaml("TSSK_TV_EPISODIO_FINAL_COLLECTION.yml", final_episode_shows, config)
        
           

        # Track all tvdbIds to exclude from the "returning" category
        all_included_tvdb_ids = set()

        # ---- New Season Shows ----
        matched_shows, skipped_shows = find_new_season_shows(
            sonarr_url, sonarr_api_key, future_days_new_season, utc_offset, skip_unmonitored
        )
        
        # Filter out shows that are in the season finale or final episode categories
        matched_shows = [show for show in matched_shows if show.get('tvdbId') not in all_excluded_tvdb_ids]
        
        # Add to excluded IDs for returning category
        for show in matched_shows:
            if show.get('tvdbId'):
                all_included_tvdb_ids.add(show['tvdbId'])
        
        if matched_shows:
            print(f"\n{GREEN}Seriados com uma nova temporada começando dentro de  {future_days_new_season} dias:{RESET}")
            for show in matched_shows:
                print(f"- {show['title']} (Temporada {show['seasonNumber']}) vai ao ar em {show['airDate']}")
        else:
            print(f"\n{RED}Nenhum show com novas estações começando dentro de {future_days_new_season} dias.{RESET}")
        
        # Create YAMLs for new seasons
        
        if IS_DOCKER:
            create_overlay_yaml(overlay_path + "08_TSSK_TV_NOVA_TEMPORADA_OVERLAYS.yml", matched_shows, 
                               {"backdrop": config.get("backdrop_new_season", config.get("backdrop", {})),
                                "text": config.get("text_new_season", config.get("text", {}))})
        
            create_collection_yaml(collection_path + "TSSK_TV_NOVA_TEMPORADA_COLLECTION.yml", matched_shows, config)
            
            os.chown(overlay_path + "08_TSSK_TV_NOVA_TEMPORADA_OVERLAYS.yml", puid, pgid)
            os.chown(collection_path + "TSSK_TV_NOVA_TEMPORADA_COLLECTION.yml", puid, pgid)

        else:
            create_overlay_yaml("08_TSSK_TV_NOVA_TEMPORADA_OVERLAYS.yml", matched_shows, 
                               {"backdrop": config.get("backdrop_new_season", config.get("backdrop", {})),
                                "text": config.get("text_new_season", config.get("text", {}))})
        
            create_collection_yaml("TSSK_TV_NOVA_TEMPORADA_COLLECTION.yml", matched_shows, config)
        
        # ---- New Season Started ----
        new_season_started_shows = find_new_season_started(
            sonarr_url, sonarr_api_key, recent_days_new_season_started, utc_offset, skip_unmonitored
        )
        
        # Add to excluded IDs
        for show in new_season_started_shows:
            if show.get('tvdbId'):
                all_excluded_tvdb_ids.add(show['tvdbId'])
        
        if new_season_started_shows:
            print(f"\n{GREEN}Seriados com uma nova temporada que começou no passado {recent_days_new_season_started} dias:{RESET}")
            for show in new_season_started_shows:
                print(f"- {show['title']} (Temporada {show['seasonNumber']}) started on {show['airDate']}")
        
        if IS_DOCKER:
            create_overlay_yaml(overlay_path + "07_TSSK_TV_NOVA_TEMPORADA_INICIADA_OVERLAYS.yml", new_season_started_shows, 
                               {"backdrop": config.get("backdrop_new_season_started", {}),
                                "text": config.get("text_new_season_started", {})})
        
            create_collection_yaml(collection_path + "TSSK_TV_NOVA_TEMPORADA_INICIADA_COLLECTION.yml", new_season_started_shows, config)

            os.chown(overlay_path + "07_TSSK_TV_NOVA_TEMPORADA_INICIADA_OVERLAYS.yml", puid, pgid)
            os.chown(collection_path + "TSSK_TV_NOVA_TEMPORADA_INICIADA_COLLECTION.yml", puid, pgid)

        else:
            create_overlay_yaml("07_TSSK_TV_NOVA_TEMPORADA_INICIADA_OVERLAYS.yml", new_season_started_shows, 
                               {"backdrop": config.get("backdrop_new_season_started", {}),
                                "text": config.get("text_new_season_started", {})})
            
            create_collection_yaml("TSSK_TV_NOVA_TEMPORADA_INICIADA_COLLECTION.yml", new_season_started_shows, config)
        
        # ---- New Episode Added ----
        if IS_DOCKER:

            create_new_episode_added_overlay_yaml(overlay_path + "03_TSSK_TV_NOVO_EPISODIO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_episode_added"),
                                        "text": get_config_section(config, "text_new_episode_added")}, 
                                       recent_days_new_episode_added)

            os.chown(overlay_path + "03_TSSK_TV_NOVO_EPISODIO_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_new_episode_added_overlay_yaml("03_TSSK_TV_NOVO_EPISODIO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_episode_added"),
                                        "text": get_config_section(config, "text_new_episode_added")}, 
                                       recent_days_new_episode_added)

        print(f"\n{GREEN}Nova Overlay Criada para série Que Tiveram um episódio adicionado recentemente em até {recent_days_new_episode_added} dias{RESET}")

        # ---- Fresh New Episode Added ----
        if IS_DOCKER:

            create_recent_new_episode_added_overlay_yaml(overlay_path + "04_TSSK_TV_NOVO_RECENTE_EPISODIO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_recent_new_episode_added"),
                                        "text": get_config_section(config, "text_recent_new_episode_added")}, 
                                       recent_days_fresh_espisode_added)

            os.chown(overlay_path + "04_TSSK_TV_NOVO_RECENTE_EPISODIO_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_recent_new_episode_added_overlay_yaml("04_TSSK_TV_NOVO_RECENTE_EPISODIO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_recent_new_episode_added"),
                                        "text": get_config_section(config, "text_recent_new_episode_added")}, 
                                       recent_days_fresh_espisode_added)

        print(f"\n{GREEN}Nova Overlay criada para series que tiveram um episódio Atual adicionado recentemente em até {recent_days_fresh_espisode_added} dias{RESET}")
       
        # ---- Fresh New Season Added ----
        if IS_DOCKER:

            create_new_season_added_overlay_yaml(overlay_path + "05_TSSK_TV_NOVO_EPISODIO_TEMPORADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_season_added"),
                                        "text": get_config_section(config, "text_new_season_added")}, 
                                       recent_days_new_season_added)

            os.chown(overlay_path + "05_TSSK_TV_NOVO_EPISODIO_TEMPORADA_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_new_season_added_overlay_yaml("05_TSSK_TV_NOVO_EPISODIO_TEMPORADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_season_added"),
                                        "text": get_config_section(config, "text_new_season_added")}, 
                                       recent_days_new_season_added)

        print(f"\n{GREEN}Nova Overlay criada para series que tiveram um episódio Atual adicionado a temporada recentemente em até {recent_days_new_season_added} dias{RESET}")

       # ---- New Show ----
        if IS_DOCKER:

            create_new_show_overlay_yaml(overlay_path + "06_TSSK_TV_NOVO_SERIADO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_show"),
                                        "text": get_config_section(config, "text_new_show")}, 
                                       recent_days_new_show)

            os.chown(overlay_path + "06_TSSK_TV_NOVO_SERIADO_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_new_show_overlay_yaml("06_TSSK_TV_NOVO_SERIADO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_show"),
                                        "text": get_config_section(config, "text_new_show")}, 
                                       recent_days_new_show)

        print(f"\n{GREEN}Nova Overlay de show criada para shows adicionados {recent_days_new_show} passados{RESET}")

       # ---- Added Episode Season - Season depth ----
        if IS_DOCKER:

            create_episode_on_season_overlay_yaml(overlay_path + "13_TSSK_TV_EPISODIO_NA_TEMPORADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_episode_season"),
                                        "text": get_config_section(config, "text_episode_season")}, 
                                       recent_days_episode_on_season)

            os.chown(overlay_path + "13_TSSK_TV_EPISODIO_NA_TEMPORADA_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_episode_on_season_overlay_yaml("13_TSSK_TV_EPISODIO_NA_TEMPORADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_episode_season"),
                                        "text": get_config_section(config, "text_episode_season")}, 
                                       recent_days_episode_on_season)
 
        print(f"\n{GREEN}Nova Overlay para temporada com episódio adicionado nos últimos {recent_days_episode_on_season} dias{RESET}")

       # ---- Added New Episode Season - Season depth ----
        if IS_DOCKER:

            create_new_episode_on_season_overlay_yaml(overlay_path + "14_TSSK_TV_NOVO_EPISODIO_NA_TEMPORADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_episode_season"),
                                        "text": get_config_section(config, "text_new_episode_season")}, 
                                       recent_days_new_episode_on_season)

            os.chown(overlay_path + "14_TSSK_TV_NOVO_EPISODIO_NA_TEMPORADA_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_new_episode_on_season_overlay_yaml("14_TSSK_TV_NOVO_EPISODIO_NA_TEMPORADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_episode_season"),
                                        "text": get_config_section(config, "text_new_episode_season")}, 
                                       recent_days_new_episode_on_season)
 
        print(f"\n{GREEN}Nova Overlay para temporada com episódio Novo adicionadonos últimos {recent_days_new_episode_on_season} dias{RESET}")
        
               # ---- Added Season - Season depth ----
        if IS_DOCKER:

            create_season_added_overlay_yaml(overlay_path + "15_TSSK_TV_TEMPORADA_ADICIONADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_season_added"),
                                        "text": get_config_section(config, "text_new_episode_season")}, 
                                       recent_days_season_added)

            os.chown(overlay_path + "15_TSSK_TV_TEMPORADA_ADICIONADA_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_season_added_overlay_yaml("15_TSSK_TV_TEMPORADA_ADICIONADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_season_added"),
                                        "text": get_config_section(config, "text_season_added")}, 
                                       recent_days_season_added)
 
        print(f"\n{GREEN}Nova Overlay para temporada adicionada nos últimos {recent_days_season_added} dias{RESET}")

               # ---- Temporada Recém-Lancada - Season depth ----
        if IS_DOCKER:

            create_new_season_released_overlay_yaml(overlay_path + "16_TSSK_TV_NOVA_TEMPORADA_ADICIONADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_season_released"),
                                        "text": get_config_section(config, "text_new_season_released")}, 
                                       recent_days_new_season_released)

            os.chown(overlay_path + "16_TSSK_TV_NOVA_TEMPORADA_ADICIONADA_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_new_season_released_overlay_yaml("16_TSSK_TV_NOVA_TEMPORADA_ADICIONADA_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_season_released"),
                                        "text": get_config_section(config, "text_new_season_released")}, 
                                       recent_days_new_season_released)
 
        print(f"\n{GREEN}Nova Overlay para Nova temporada adicionada nos últimos {recent_days_new_season_released} dias{RESET}")
        
        
                       # ---- Episódio Recém-Adicionado - Episode depth ----
        if IS_DOCKER:

            create_episode_added_overlay_yaml(overlay_path + "17_TSSK_TV_EPISODIO_ADICIONADO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_episode_added"),
                                        "text": get_config_section(config, "text_episode_added")}, 
                                       recent_days_episode_added)

            os.chown(overlay_path + "17_TSSK_TV_EPISODIO_ADICIONADO_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_episode_added_overlay_yaml("17_TSSK_TV_EPISODIO_ADICIONADO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_episode_added"),
                                        "text": get_config_section(config, "text_episode_added")}, 
                                       recent_days_episode_added)
 
        print(f"\n{GREEN}Nova Overlay para Episódio adicionado nos últimos {recent_days_episode_added} dias{RESET}")

                       # ---- Episódio Recém-Lançado - Episode depth ----
        if IS_DOCKER:

            create_new_episode_released_overlay_yaml(overlay_path + "18_TSSK_TV_NOVO_EPISODIO_ADICIONADO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_episode_released"),
                                        "text": get_config_section(config, "text_new_episode_released")}, 
                                       recent_days_new_episode_released)

            os.chown(overlay_path + "18_TSSK_TV_NOVO_EPISODIO_ADICIONADO_OVERLAYS.yml", puid, pgid) 
        else:
            
            create_new_episode_released_overlay_yaml("18_TSSK_TV_NOVO_EPISODIO_ADICIONADO_OVERLAYS.yml", 
                                       {"backdrop": get_config_section(config, "backdrop_new_episode_released"),
                                        "text": get_config_section(config, "text_new_episode_released")}, 
                                       recent_days_new_episode_released)
 
        print(f"\n{GREEN}Nova Overlay para Episódio adicionado nos últimos {recent_days_new_episode_released} days{RESET}")        
        
        # ---- Upcoming Non-Finale Episodes ----
        upcoming_eps, skipped_eps = find_upcoming_regular_episodes(
            sonarr_url, sonarr_api_key, future_days_upcoming_episode, utc_offset, skip_unmonitored
        )
        
        # Filter out shows that are in the season finale or final episode categories
        upcoming_eps = [show for show in upcoming_eps if show.get('tvdbId') not in all_excluded_tvdb_ids]
        
        # Add to excluded IDs for returning category
        for show in upcoming_eps:
            if show.get('tvdbId'):
                all_included_tvdb_ids.add(show['tvdbId'])
        
        if upcoming_eps:
            print(f"\n{GREEN}Seriados com os próximos episódios não finas em  até {future_days_upcoming_episode} dias:{RESET}")
            for show in upcoming_eps:
                print(f"- {show['title']} (S{show['seasonNumber']}E{show['episodeNumber']}) vai ao ar em {show['airDate']}")
        
        if IS_DOCKER:

            create_overlay_yaml(overlay_path + "09_TSSK_TV_PROXIMOS_EPISODIOS_OVERLAYS.yml", upcoming_eps, 
                               {"backdrop": config.get("backdrop_upcoming_episode", {}),
                                "text": config.get("text_upcoming_episode", {})})
        
            create_collection_yaml(collection_path + "TSSK_TV_PROXIMOS_EPISODIOS_COLLECTION.yml", upcoming_eps, config)

            os.chown(overlay_path + "09_TSSK_TV_PROXIMOS_EPISODIOS_OVERLAYS.yml", puid, pgid)
            os.chown(collection_path + "TSSK_TV_PROXIMOS_EPISODIOS_COLLECTION.yml", puid, pgid)
           
        else:
            create_overlay_yaml("09_TSSK_TV_PROXIMOS_EPISODIOS_OVERLAYS.yml", upcoming_eps, 
                               {"backdrop": config.get("backdrop_upcoming_episode", {}),
                                "text": config.get("text_upcoming_episode", {})})
        
            create_collection_yaml("TSSK_TV_PROXIMOS_EPISODIOS_COLLECTION.yml", upcoming_eps, config)
        

        # ---- Upcoming Finale Episodes ----
        finale_eps, skipped_finales = find_upcoming_finales(
            sonarr_url, sonarr_api_key, future_days_upcoming_finale, utc_offset, skip_unmonitored
        )
        
        # Filter out shows that are in the season finale or final episode categories
        finale_eps = [show for show in finale_eps if show.get('tvdbId') not in all_excluded_tvdb_ids]
        
        # Add to excluded IDs for returning category
        for show in finale_eps:
            if show.get('tvdbId'):
                all_included_tvdb_ids.add(show['tvdbId'])
        
        if finale_eps:
            print(f"\n{GREEN}Seriados com as próximas finais da temporada dentro de {future_days_upcoming_finale} dias:{RESET}")
            for show in finale_eps:
                print(f"- {show['title']} (S{show['seasonNumber']}E{show['episodeNumber']}) vai ao ar em {show['airDate']}")
        
        if IS_DOCKER:
            create_overlay_yaml(overlay_path + "10_TSSK_TV_PROXIMOS_FINAIS_OVERLAYS.yml", finale_eps, 
                               {"backdrop": config.get("backdrop_upcoming_finale", {}),
                                "text": config.get("text_upcoming_finale", {})})
        
            create_collection_yaml(collection_path + "TSSK_TV_PROXIMOS_FINAIS_COLLECTION.yml", finale_eps, config)
            os.chown(overlay_path + "10_TSSK_TV_PROXIMOS_FINAIS_OVERLAYS.yml", puid, pgid)
            os.chown(collection_path + "TSSK_TV_PROXIMOS_FINAIS_COLLECTION.yml", puid, pgid)

        else:
            create_overlay_yaml("10_TSSK_TV_PROXIMOS_FINAIS_OVERLAYS.yml", finale_eps, 
                               {"backdrop": config.get("backdrop_upcoming_finale", {}),
                                "text": config.get("text_upcoming_finale", {})})
        
            create_collection_yaml("TSSK_TV_PROXIMOS_FINAIS_COLLECTION.yml", finale_eps, config)
        
        # ---- skipped Shows ----
        if skipped_shows:
            print(f"\n{ORANGE}Seriados (não monitorados ou novos shows):{RESET}")
            for show in skipped_shows:
                print(f"- {show['title']} (Temporada {show['seasonNumber']}) vai ao ar em {show['airDate']}")        
        
        # ---- Ended Shows ----
        # The find_ended_shows function doesn't have a skip_unmonitored parameter
        # as it's based on show status rather than monitoring status
        ended_shows, cancelled_shows = find_ended_shows(
            sonarr_url, sonarr_api_key, tmdb_api_key
        )
        # Filter out shows that are in the season finale or final episode categories
        ended_shows = [
            show
            for show in ended_shows
            if show.get("tvdbId") not in all_excluded_tvdb_ids
        ]
        cancelled_shows = [
            show
            for show in cancelled_shows
            if show.get("tvdbId") not in all_excluded_tvdb_ids
        ]

        # Add to excluded IDs for returning category
        for show in ended_shows:
            if show.get("tvdbId"):
                all_included_tvdb_ids.add(show["tvdbId"])

        for show in cancelled_shows:
            if show.get("tvdbId"):
                all_included_tvdb_ids.add(show["tvdbId"])

        # ---- Cancelled Shows ----
        if cancelled_shows:
                    print(f"\n{GREEN}Seriados que foram Cancelados:{RESET}")
                    for show in cancelled_shows:
                        print(f"- {show['title']}")
                        
        if IS_DOCKER:
            create_overlay_yaml(overlay_path + "00_TSSK_TV_CANCELADOS_OVERLAYS.yml", cancelled_shows, 
                               {"backdrop": config.get("backdrop_cancelled", {}),
                                "text": config.get("text_cancelled", {})})
        
            create_collection_yaml(collection_path + "TSSK_TV_CANCELADOS_COLLECTION.yml", cancelled_shows, config)
            
            os.chown(overlay_path + "00_TSSK_TV_CANCELADOS_OVERLAYS.yml", puid, pgid)
            os.chown(collection_path + "TSSK_TV_CANCELADOS_COLLECTION.yml", puid, pgid)

        else:
            create_overlay_yaml("00_TSSK_TV_CANCELADOS_OVERLAYS.yml", cancelled_shows, 
                               {"backdrop": config.get("backdrop_cancelled", {}),
                                "text": config.get("text_cancelled", {})})
        
            create_collection_yaml("TSSK_TV_CANCELADOS_COLLECTION.yml", cancelled_shows, config)
        
        # ---- Ended Shows ----
        if ended_shows:
                    print(f"\n{GREEN}Seriados já Finalizados:{RESET}")
                    for show in ended_shows:
                        print(f"- {show['title']}")
        if IS_DOCKER:
            create_overlay_yaml(overlay_path + "01_TSSK_TV_FINALIZADOS_OVERLAYS.yml", ended_shows, 
                               {"backdrop": config.get("backdrop_ended", {}),
                                "text": config.get("text_ended", {})})
        
            create_collection_yaml(collection_path + "TSSK_TV_FINALIZADOS_COLLECTION.yml", ended_shows, config)
            os.chown(overlay_path + "01_TSSK_TV_FINALIZADOS_OVERLAYS.yml", puid, pgid)
            os.chown(collection_path + "TSSK_TV_FINALIZADOS_COLLECTION.yml", puid, pgid)

        else:
            create_overlay_yaml("01_TSSK_TV_FINALIZADOS_OVERLAYS.yml", ended_shows, 
                               {"backdrop": config.get("backdrop_ended", {}),
                                "text": config.get("text_ended", {})})
        
            create_collection_yaml("TSSK_TV_FINALIZADOS_COLLECTION.yml", ended_shows, config)
        
        # ---- Returning Shows ----
        returning_shows = find_returning_shows(sonarr_url, sonarr_api_key, all_included_tvdb_ids)
        
        # Filter out shows that are in the season finale or final episode categories
        returning_shows = [show for show in returning_shows if show.get('tvdbId') not in all_excluded_tvdb_ids]
        
        if returning_shows:
            print(f"\n{GREEN}Seriados que não foram cancelados, mas não tem data de retorno:{RESET}")
            for show in returning_shows:
                print(f"- {show['title']}")
        
        if IS_DOCKER:
            create_overlay_yaml(overlay_path + "02_TSSK_TV_RETORNANDO_OVERLAYS.yml", returning_shows, 
                               {"backdrop": config.get("backdrop_returning", {}),
                                "text": config.get("text_returning", {})})
        
            create_collection_yaml(collection_path + "TSSK_TV_RETORNANDO_COLLECTION.yml", returning_shows, config)
            os.chown(overlay_path + "02_TSSK_TV_RETORNANDO_OVERLAYS.yml", puid, pgid)
            os.chown(collection_path + "TSSK_TV_RETORNANDO_COLLECTION.yml", puid, pgid)

        else:
            create_overlay_yaml("02_TSSK_TV_RETORNANDO_OVERLAYS.yml", returning_shows, 
                               {"backdrop": config.get("backdrop_returning", {}),
                                "text": config.get("text_returning", {})})
        
            create_collection_yaml("TSSK_TV_RETORNANDO_COLLECTION.yml", returning_shows, config)
        

        print(f"\nTodos os arquivos YAML criados com sucesso")

        # Calculate and display runtime
        end_time = datetime.now()
        runtime = end_time - start_time
        hours, remainder = divmod(runtime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        runtime_formatted = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        
        print(f"{BLUE}{BLUE}{'*' * 110}\n{'*' * 3}{' ' * 5}Inicio do Processo: {start_time.strftime('%H:%M:%S')}{' ' * 4}Fim do Processo: {end_time.strftime('%H:%M:%S')}{' ' * 4}Tempo Total de Execução: {runtime_formatted}{' ' * 5}{'*' * 3}\n{'*' * 110}")

    except ConnectionError as e:
        print(f"{RED}Error: {str(e)}{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}Unexpected error: {str(e)}{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
