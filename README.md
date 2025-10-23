#  Price Tracker Discord Bot

Un bot completo para **monitorear precios de productos del sitio [ComprasParaguai.com.br](https://www.comprasparaguai.com.br/)** directamente desde **Discord**, con soporte para **comandos de barra (/)**, historial de precios y alertas automáticas en tiempo real.

---

##  Funcionalidades

 **Seguimiento Automático**
- Revisa periódicamente los precios de los productos monitoreados.  
- Envía alertas automáticas cuando el precio **sube** o **baja**, incluyendo:
  - Nombre del producto  
  - Precio anterior y nuevo  
  - Porcentaje de variación  
  - Precio más bajo registrado y su fecha  
  - Enlace directo al producto  

 **Comandos Slash**
| Comando | Descripción |
|----------|-------------|
| `/seguir [link]` | Agrega un producto para monitorear |
| `/consulta [nombre]` | Busca precios actuales en ComprasParaguai |
| `/lista` | Muestra todos los productos que están siendo monitoreados, con sus precios e historial |
| `/remover [nombre o link]` | Elimina un producto de la lista de seguimiento |

 **Base de Datos Local**
- Guarda el historial de precios y el menor precio registrado.  
- Mantiene los datos aunque el bot se reinicie.

---

##  Tecnologías Utilizadas

- [Python 3.11+](https://www.python.org/)
- [discord.py (app_commands)](https://discordpy.readthedocs.io/)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)
- [aiohttp](https://docs.aiohttp.org/)
- [SQLite3](https://www.sqlite.org/index.html)
- [dotenv](https://pypi.org/project/python-dotenv/)

---

##  Cómo usar el bot

1. Abre Discord y entra en **App Directory** (Tienda de Bots).
2. Busca: **Meura do Pix™**
3. Haz clic en **Añadir al servidor**
4. Usa los comandos `/seguir`, `/consulta`, `/lista` o `/remover` directamente en tu servidor.

---

##  Autor

**Diego Groppo**  
 Mar del Plata, Argentina  
 Discord: `die.god`  
 GitHub: [diegogr05](https://github.com/diegogr05)

---

##  Licencia

Este proyecto se distribuye bajo la licencia **MIT**.  
Puedes usarlo, modificarlo y compartirlo libremente.

---

