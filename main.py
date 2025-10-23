import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime
from config import TOKEN, CHECK_INTERVAL_MINUTES, NOTIFY_CHANNEL_ID
from database import init_db, get_all_items, update_price, add_item, remove_item_by_url_or_name, get_min_price
from scraper import scrape_product_page, fetch_html
import threading
import http.server
import socketserver

def percent_change(old, new):
    try:
        return ((new - old) / old) * 100.0
    except:
        return None

def format_change_emoji(change):
    if change is None:
        return ''
    if change > 0:
        return f'🟢 Subiu {abs(change):.2f}%'
    elif change < 0:
        return f'🔴 Baixou {abs(change):.2f}%'
    else:
        return '➡️ Sem alteração'

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Logado como {bot.user} (ID: {bot.user.id}) - {datetime.utcnow()}')
    await init_db()
    check_prices.start()
    try:
        await bot.tree.sync()
        print('🌍 Comandos / sincronizados.')
    except Exception as e:
        print('Erro ao sincronizar comandos:', e)

@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def check_prices():
    print('🔁 Verificando preços...', datetime.utcnow())
    items = await get_all_items()
    for item_id, guild_id, channel_id, url, product_name, last_price, currency in items:
        name, price, curr = await scrape_product_page(url)
        if price is None:
            print('❌ Preço não encontrado:', url)
            continue
        if last_price is None:
            await update_price(item_id, price, curr)
            continue
        if price != last_price:
            change = percent_change(last_price, price)
            emoji = format_change_emoji(change)
            min_price, min_date, min_curr = await get_min_price(item_id)
            min_line = ''
            if min_price is not None:
                min_line = f'📉 Menor preço registrado: {min_price:.2f} {min_curr or curr} ({min_date.split(" ")[0]})\n'

            msg = (
                f'📦 **{name}**\n'
                f'💰 Preço antigo: {last_price:.2f} {currency}\n'
                f'💵 Novo preço: {price:.2f} {curr}\n'
                f'{emoji}\n'
                f'{min_line}'
                f'🔗 [Abrir produto]({url})'
            )
            try:
                channel = None
                if NOTIFY_CHANNEL_ID:
                    channel = bot.get_channel(int(NOTIFY_CHANNEL_ID))
                if not channel:
                    channel = bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(msg)
            except Exception as e:
                print('Erro ao enviar notificação:', e)
            await update_price(item_id, price, curr)

@bot.tree.command(name='seguir', description='Começar a monitorar um produto (link do ComprasParaguai)')
@app_commands.describe(link='Link direto do produto')
async def seguir(interaction: discord.Interaction, link: str):
    try:
        await interaction.response.defer(thinking=True)
        name, price, curr = await scrape_product_page(link)
        if price is None:
            await interaction.followup.send('❌ Não foi possível extrair o preço desse link.', ephemeral=True)
            return
        await add_item(str(interaction.guild_id), str(interaction.channel_id), link, name, price, curr)
        await interaction.followup.send(f'✅ Comecei a monitorar **{name}** por {price:.2f} {curr}.')
    except Exception as e:
        print(f"Erro em /seguir: {e}")
        try:
            await interaction.followup.send('⚠️ Ocorreu um erro ao tentar seguir o produto.', ephemeral=True)
        except:
            pass

@bot.tree.command(name='consulta', description='Buscar preço(s) no ComprasParaguai por nome')
@app_commands.describe(query='Nome do produto (busca)')
async def consulta(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)
    search_url = f"https://www.comprasparaguai.com.br/busca/?s={query.replace(' ', '+')}"
    html = await fetch_html(search_url)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    for a in soup.select('a[href]'):
        href = a.get('href')
        if href and ("/produto" in href or "/produto-" in href or "/produto/" in href):
            if href.startswith('/'):
                href = 'https://www.comprasparaguai.com.br' + href
            if href not in [r[0] for r in results]:
                results.append((href, a.get_text(strip=True)))
        if len(results) >= 3:
            break
    if not results:
        await interaction.followup.send('Nenhum resultado encontrado.')
        return
    messages = []
    from scraper import scrape_product_page as spp
    for url, title in results:
        n, p, c = await spp(url)
        if p:
            messages.append(f"**{n}** — {p:.2f} {c}\n{url}")
        else:
            messages.append(f"**{title or url}** — preço não encontrado\n{url}")
    await interaction.followup.send("\n\n".join(messages))

@bot.tree.command(name='lista', description='Listar todos os produtos monitorados neste servidor')
async def lista(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    items = await get_all_items()
    guild_items = [i for i in items if str(i[1]) == str(interaction.guild_id)]
    if not guild_items:
        await interaction.followup.send('Nenhum produto está sendo monitorado neste servidor.')
        return
    parts = []
    for item_id, _, _, url, name, last_price, curr in guild_items:
        min_price, min_date, min_curr = await get_min_price(item_id)
        min_line = f"📉 Menor preço registrado: {min_price:.2f} {min_curr or curr} ({min_date.split(' ')[0]})" if min_price is not None else "📉 Menor preço registrado: —"
        parts.append(
            f"📦 **{name}**\n"
            f"💵 Preço atual: {last_price:.2f} {curr}\n"
            f"{min_line}\n"
            f"🔗 [Abrir produto]({url})"
        )
    await interaction.followup.send("\n\n".join(parts))

@bot.tree.command(name='remover', description='Remover um item do monitoramento (nome ou link)')
@app_commands.describe(query='Nome do produto ou link')
async def remover(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)
    ok = await remove_item_by_url_or_name(str(interaction.guild_id), query)
    await interaction.followup.send('✅ Item removido.' if ok else '❌ Não encontrei item com esse nome ou link.')

# 🔹 Fake server (necessário para Render não encerrar a instância)
def keep_alive():
    PORT = 8080
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🌐 Servidor falso rodando na porta {PORT}")
        httpd.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    if not TOKEN:
        print('ERROR: DISCORD_TOKEN não configurado. Edite o arquivo .env')
    else:
        bot.run(TOKEN)
