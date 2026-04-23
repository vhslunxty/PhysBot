import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import json
from datetime import datetime, timedelta
import asyncio
import random
import socket
import struct
from keep_alive import keep_alive

CONFIG = {
    "token": "",  # ← Mettez votre token Discord ici
    "prefix": "+",
    "color": 0x2B2D31,
    "owner_id": 1440071896308781086, 
    "name": "", # ← Mettez le name du BOT
    "ticket_channel_id": 453431, # ← Mettez ID du channel ticket
    "gmod_server": {
        "enabled": True,
        "ip": "194.69.160.12",
        "port": 27060,
        "name": "GMod BOT + Discord BOT" # ← Mettez votre nom serveur GMod ( Retrouvable dans server.cfg )
    }
}

DATABASE = {
    "sanctions": {},
    "mutes": {},
    "config": {
        "welcome_channel": None,
        "log_channel": None,
        "antiraid_enabled": False,
        "logs_category": None,
        "log_channels": {}
    },
    "snipe": {},
    "tickets": {},
    "giveaways": {},
    "permissions": {}
}

PERMISSIONS = {
    "perm1": {
        "name": "🔰 Modérateur Junior",
        "commands": ["warn", "mute", "unmute", "tempmute"],
        "color": 0x3498db
    },
    "perm2": {
        "name": "🛡️ Modérateur",
        "commands": ["warn", "mute", "unmute", "tempmute", "kick", "tempban"],
        "color": 0x9b59b6
    },
    "perm3": {
        "name": "⚔️ Modérateur Senior",
        "commands": ["warn", "mute", "unmute", "tempmute", "kick", "ban", "unban", "clear"],
        "color": 0xe74c3c
    },
    "perm_all": {
        "name": "👑 Administrateur",
        "commands": ["all"],
        "color": 0xf1c40f
    }
}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=CONFIG["prefix"], intents=intents, help_command=None)

def is_owner_or_admin():
    async def predicate(ctx):
        return ctx.author.id == CONFIG["owner_id"] or ctx.author.guild_permissions.administrator
    return commands.check(predicate)

def has_perm_level(required_command):
    async def predicate(ctx):
        if ctx.author.id == CONFIG["owner_id"] or ctx.author.guild_permissions.administrator:
            return True
        user_perm = DATABASE["permissions"].get(ctx.author.id)
        if not user_perm:
            return False
        perm_data = PERMISSIONS.get(user_perm)
        if perm_data:
            if "all" in perm_data["commands"] or required_command in perm_data["commands"]:
                return True
        return False
    return commands.check(predicate)

def create_embed(title, description, color=CONFIG["color"]):
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
    if bot.user and bot.user.avatar:
        embed.set_footer(text=CONFIG["name"], icon_url=bot.user.avatar.url)
    else:
        embed.set_footer(text=CONFIG["name"])
    return embed

def add_sanction(user_id, sanction_type, reason, moderator):
    if user_id not in DATABASE["sanctions"]:
        DATABASE["sanctions"][user_id] = []
    DATABASE["sanctions"][user_id].append({
        "type": sanction_type,
        "reason": reason,
        "moderator": moderator,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

async def log_action(guild, action_type, embed):
    log_channels = DATABASE["config"].get("log_channels", {})
    channel_id = log_channels.get(action_type)
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)


def query_gmod_server(ip, port, timeout=3):
    """Interroge un serveur Source (GMod) pour obtenir les infos"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # A2S_INFO request packet
        packet = b'\xFF\xFF\xFF\xFF\x54Source Engine Query\x00'
        sock.sendto(packet, (ip, port))
        data = sock.recv(4096)
        sock.close()
        
        if len(data) < 6:
            return None
        
        offset = 5
        offset += 1
        
        server_name_end = data.find(b'\x00', offset)
        if server_name_end == -1:
            return None
        server_name = data[offset:server_name_end].decode('utf-8', errors='ignore')
        offset = server_name_end + 1
        
        map_name_end = data.find(b'\x00', offset)
        if map_name_end == -1:
            return None
        offset = map_name_end + 1
        
        folder_end = data.find(b'\x00', offset)
        if folder_end == -1:
            return None
        offset = folder_end + 1
        
        game_end = data.find(b'\x00', offset)
        if game_end == -1:
            return None
        offset = game_end + 1
        
        if offset + 2 > len(data):
            return None
        offset += 2
        
        if offset + 1 > len(data):
            return None
        players = struct.unpack('B', data[offset:offset+1])[0]
        offset += 1
        
        if offset + 1 > len(data):
            return None
        max_players = struct.unpack('B', data[offset:offset+1])[0]
        
        if players == 255 or max_players == 255 or max_players == 0:
            print(f"⚠️ Données incohérentes du serveur: {players}/{max_players}")
            return None
        
        if players > max_players:
            print(f"⚠️ Nombre de joueurs invalide: {players}/{max_players}")
            return None
        
        return {
            "name": server_name,
            "players": players,
            "max_players": max_players,
            "online": True
        }
    
    except socket.timeout:
        print(f"⏱️ Timeout lors de la connexion au serveur GMod")
        return None
    except socket.error as e:
        print(f"❌ Erreur réseau: {e}")
        return None
    except Exception as e:
        print(f"❌ Erreur query serveur GMod: {e}")
        return None

@tasks.loop(seconds=30)
async def update_gmod_status():
    """Met à jour le statut du bot avec les infos du serveur GMod"""
    if not CONFIG["gmod_server"]["enabled"]:
        return
    
    server_info = query_gmod_server(
        CONFIG["gmod_server"]["ip"],
        CONFIG["gmod_server"]["port"]
    )
    
    if server_info:
        status_text = f"👀 {CONFIG['gmod_server']['name']} | {server_info['players']}/{server_info['max_players']} joueurs"
        activity = discord.Game(name=status_text)
        await bot.change_presence(activity=activity, status=discord.Status.online)
    else:
        status_text = "Serveur Hors Ligne !"
        activity = discord.Game(name=status_text)
        await bot.change_presence(activity=activity, status=discord.Status.idle)
    
    try:
        await update_gmod_embed(server_info)
    except Exception as e:
        print(f"⚠️ Erreur mise à jour embed: {e}")

async def update_gmod_embed(server_info):
    """Met à jour l'embed du serveur GMod dans le salon configuré"""
    message_id = DATABASE["config"].get("gmod_embed_message_id")
    channel_id = DATABASE["config"].get("gmod_embed_channel_id")
    
    if not message_id or not channel_id:
        return
    
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"❌ Salon {channel_id} introuvable pour l'embed GMod")
            return
        
        message = await channel.fetch_message(message_id)
        
        if server_info and server_info.get("online"):
            embed = discord.Embed(
                title=f"🎮 {CONFIG['gmod_server']['name']}",
                description=f"**Connectez-vous:** `connect {CONFIG['gmod_server']['ip']}:{CONFIG['gmod_server']['port']}`",
                color=0x2ecc71,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📊 Statut", value="🟢 **En ligne**", inline=True)
            embed.add_field(name="👥 Joueurs", value=f"**{server_info['players']}/{server_info['max_players']}**", inline=True)
            embed.add_field(name="📡 Ping", value="✅ **Actif**", inline=True)
            
            percentage = (server_info['players'] / server_info['max_players']) * 100 if server_info['max_players'] > 0 else 0
            filled = int(percentage / 10)
            bar = "🟩" * filled + "⬜" * (10 - filled)
            embed.add_field(name="📈 Occupation du serveur", value=f"{bar}\n**{percentage:.1f}%** - {server_info['players']} joueur(s) connecté(s)", inline=False)
            
            embed.set_footer(text=f"🔄 Mise à jour automatique toutes les 30s • {CONFIG['name']}")
            
            print(f"✅ Embed mis à jour : {server_info['players']}/{server_info['max_players']} joueurs")
            
        else:
            embed = discord.Embed(
                title=f"🎮 {CONFIG['gmod_server']['name']}",
                description=f"**IP:** `{CONFIG['gmod_server']['ip']}:{CONFIG['gmod_server']['port']}`",
                color=0xe74c3c,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📊 Statut", value="🔴 **Hors ligne**", inline=True)
            embed.add_field(name="👥 Joueurs", value="**0/0**", inline=True)
            embed.add_field(name="📡 Ping", value="❌ **Inactif**", inline=True)
            
            embed.add_field(name="⚠️ Information", value="Le serveur ne répond pas actuellement.\nIl est peut-être en redémarrage ou maintenance.", inline=False)
            
            embed.set_footer(text=f"🔄 Mise à jour automatique toutes les 30s • {CONFIG['name']}")
            
            print("⚠️ Embed mis à jour : Serveur hors ligne")
        
        await message.edit(embed=embed)
    
    except discord.NotFound:
        print("❌ Message de l'embed GMod introuvable, il a peut-être été supprimé")
        DATABASE["config"]["gmod_embed_message_id"] = None
        DATABASE["config"]["gmod_embed_channel_id"] = None
    except discord.Forbidden:
        print("❌ Pas les permissions pour modifier l'embed GMod")
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour de l'embed: {e}")


class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="💬 Assistance Générale", style=discord.ButtonStyle.blurple, custom_id="ticket_help")
    async def help_button(self, interaction: discord.Interaction, button: Button):
        await self.create_ticket(interaction, "Assistance Générale", "💬", 0x3498db)
    
    @discord.ui.button(label="🎭 Demande RP", style=discord.ButtonStyle.green, custom_id="ticket_rp")
    async def rp_button(self, interaction: discord.Interaction, button: Button):
        await self.create_ticket(interaction, "Demande RP", "🎭", 0x2ecc71)
    
    @discord.ui.button(label="👔 Contact Staff", style=discord.ButtonStyle.red, custom_id="ticket_staff")
    async def staff_button(self, interaction: discord.Interaction, button: Button):
        await self.create_ticket(interaction, "Contact Staff", "👔", 0xe74c3c)
    
    async def create_ticket(self, interaction: discord.Interaction, category_name, emoji, color):
        guild = interaction.guild
        user = interaction.user
        
        for channel in guild.text_channels:
            if channel.name == f"ticket-{user.name.lower()}":
                return await interaction.response.send_message("❌ Vous avez déjà un ticket ouvert !", ephemeral=True)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{user.name}",
            overwrites=overwrites,
            topic=f"{category_name} - Créé par {user.name}"
        )
        
        DATABASE["tickets"][ticket_channel.id] = {
            "user_id": user.id,
            "category": category_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        embed = create_embed(
            f"{emoji} {category_name}",
            f"**Bienvenue {user.mention} !**\n\n"
            f"Merci d'avoir ouvert un ticket.\n"
            f"Un membre du staff va vous répondre sous peu.\n\n"
            f"**Catégorie:** {category_name}\n"
            f"**Créé le:** {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            color
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        close_view = View(timeout=None)
        close_button = Button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id=f"close_{ticket_channel.id}")
        
        async def close_callback(btn_interaction: discord.Interaction):
            if btn_interaction.user.guild_permissions.manage_channels or btn_interaction.user.id == user.id:
                await btn_interaction.response.send_message("🔒 Fermeture du ticket dans 5 secondes...", ephemeral=True)
                await asyncio.sleep(5)
                await ticket_channel.delete()
                if ticket_channel.id in DATABASE["tickets"]:
                    del DATABASE["tickets"][ticket_channel.id]
            else:
                await btn_interaction.response.send_message("❌ Vous n'avez pas la permission !", ephemeral=True)
        
        close_button.callback = close_callback
        close_view.add_item(close_button)
        
        await ticket_channel.send(f"{user.mention}", embed=embed, view=close_view)
        await interaction.response.send_message(f"✅ Ticket créé : {ticket_channel.mention}", ephemeral=True)

@bot.command(name='setupticket')
@is_owner_or_admin()
async def setup_ticket(ctx):
    embed = create_embed(
        "🎫 Système de Tickets",
        "**Besoin d'aide ? Ouvrez un ticket !**\n\n"
        "Cliquez sur un des boutons ci-dessous selon votre besoin :\n\n"
        "💬 **Assistance Générale** - Questions générales\n"
        "🎭 **Demande RP** - Questions roleplay\n"
        "👔 **Contact Staff** - Contacter un responsable",
        0x5865F2
    )
    view = TicketView()
    await ctx.send(embed=embed, view=view)
    await ctx.message.delete()


@bot.command(name='gstart')
@is_owner_or_admin()
async def giveaway_start(ctx, duration: str, winners: int, *, prize: str):
    time_unit = duration[-1]
    time_value = int(duration[:-1])
    
    if time_unit == 'm':
        end_time = datetime.now() + timedelta(minutes=time_value)
    elif time_unit == 'h':
        end_time = datetime.now() + timedelta(hours=time_value)
    elif time_unit == 'd':
        end_time = datetime.now() + timedelta(days=time_value)
    else:
        return await ctx.send("❌ Format invalide ! Utilisez : 1m, 1h ou 1d")
    
    embed = create_embed(
        "🎉 GIVEAWAY 🎉",
        f"**Prix:** {prize}\n"
        f"**Gagnants:** {winners}\n"
        f"**Fin:** <t:{int(end_time.timestamp())}:R>\n"
        f"**Organisé par:** {ctx.author.mention}\n\n"
        f"Réagissez avec 🎉 pour participer !",
        0xe74c3c
    )
    embed.set_footer(text=f"{winners} gagnant(s)")
    embed.timestamp = end_time
    
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")
    
    DATABASE["giveaways"][msg.id] = {
        "channel_id": ctx.channel.id,
        "prize": prize,
        "winners": winners,
        "end_time": end_time.timestamp(),
        "host_id": ctx.author.id
    }
    
    await ctx.message.delete()

@tasks.loop(seconds=30)
async def check_giveaways():
    current_time = datetime.now().timestamp()
    to_remove = []
    
    for msg_id, giveaway in DATABASE["giveaways"].items():
        if current_time >= giveaway["end_time"]:
            channel = bot.get_channel(giveaway["channel_id"])
            if channel:
                try:
                    message = await channel.fetch_message(msg_id)
                    reaction = discord.utils.get(message.reactions, emoji="🎉")
                    
                    if reaction:
                        users = [user async for user in reaction.users() if not user.bot]
                        
                        if len(users) >= giveaway["winners"]:
                            winners = random.sample(users, giveaway["winners"])
                            winner_mentions = ", ".join([w.mention for w in winners])
                            
                            embed = create_embed(
                                "🎉 GIVEAWAY TERMINÉ 🎉",
                                f"**Prix:** {giveaway['prize']}\n**Gagnants:** {winner_mentions}",
                                0x2ecc71
                            )
                            await channel.send(f"🎊 Félicitations {winner_mentions} !", embed=embed)
                        else:
                            await channel.send("❌ Pas assez de participants !")
                    to_remove.append(msg_id)
                except:
                    to_remove.append(msg_id)
    
    for msg_id in to_remove:
        del DATABASE["giveaways"][msg_id]

@bot.command(name='gend')
@is_owner_or_admin()
async def giveaway_end(ctx, message_id: int):
    if message_id in DATABASE["giveaways"]:
        DATABASE["giveaways"][message_id]["end_time"] = datetime.now().timestamp()
        await ctx.send("✅ Le giveaway va se terminer !")
    else:
        await ctx.send("❌ Giveaway introuvable !")

@bot.command(name='greroll')
@is_owner_or_admin()
async def giveaway_reroll(ctx, message_id: int):
    try:
        message = await ctx.channel.fetch_message(message_id)
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        if reaction:
            users = [user async for user in reaction.users() if not user.bot]
            if users:
                winner = random.choice(users)
                await ctx.send(f"🎊 Nouveau gagnant : {winner.mention} !")
            else:
                await ctx.send("❌ Aucun participant !")
    except:
        await ctx.send("❌ Message introuvable !")


@bot.command(name='logs')
@is_owner_or_admin()
async def setup_logs(ctx):
    guild = ctx.guild
    category = await guild.create_category("📊 LOGS")
    DATABASE["config"]["logs_category"] = category.id
    
    log_channels = {
        "messages": ("📝-logs-messages", "Logs des messages"),
        "voice": ("🔊-logs-vocaux", "Logs vocaux"),
        "members": ("👥-logs-membres", "Logs des membres"),
        "moderation": ("🛡️-logs-modération", "Logs modération"),
        "server": ("⚙️-logs-serveur", "Logs serveur")
    }
    
    for log_type, (name, topic) in log_channels.items():
        channel = await guild.create_text_channel(name=name, category=category, topic=topic)
        DATABASE["config"]["log_channels"][log_type] = channel.id
    
    embed = create_embed(
        "✅ Système de Logs Configuré",
        f"Catégorie créée : {category.mention}\n\n**Salons créés:**\n"
        f"📝 Messages | 🔊 Vocaux | 👥 Membres\n🛡️ Modération | ⚙️ Serveur",
        0x2ecc71
    )
    await ctx.send(embed=embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    DATABASE["snipe"][message.channel.id] = {
        "content": message.content,
        "author": str(message.author),
        "time": datetime.now()
    }
    embed = create_embed(
        "🗑️ Message Supprimé",
        f"**Auteur:** {message.author.mention}\n**Salon:** {message.channel.mention}\n"
        f"**Contenu:** {message.content[:1024] if message.content else '*Vide*'}",
        0xe74c3c
    )
    await log_action(message.guild, "messages", embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    embed = create_embed(
        "✏️ Message Modifié",
        f"**Auteur:** {before.author.mention}\n**Salon:** {before.channel.mention}\n"
        f"**Avant:** {before.content[:512]}\n**Après:** {after.content[:512]}",
        0xf39c12
    )
    await log_action(before.guild, "messages", embed)

@bot.event
async def on_member_join(member):
    embed = create_embed(
        "📥 Membre Rejoint",
        f"**Membre:** {member.mention}\n**ID:** {member.id}\n"
        f"**Compte créé:** <t:{int(member.created_at.timestamp())}:R>\n"
        f"**Membres:** {member.guild.member_count}",
        0x2ecc71
    )
    await log_action(member.guild, "members", embed)
    
    channel_id = DATABASE["config"].get("welcome_channel")
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel:
            embed = create_embed(
                "👋 Bienvenue !",
                f"Bienvenue {member.mention} sur **{member.guild.name}** !\n\n"
                f"Nous sommes maintenant **{member.guild.member_count}** membres !",
                0x00FF00
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    embed = create_embed(
        "📤 Membre Parti",
        f"**Membre:** {member.mention}\n**ID:** {member.id}\n"
        f"**Rejoint:** <t:{int(member.joined_at.timestamp())}:R>\n"
        f"**Membres:** {member.guild.member_count}",
        0xe74c3c
    )
    await log_action(member.guild, "members", embed)

@bot.command(name='addperm')
@is_owner_or_admin()
async def add_perm(ctx, member: discord.Member, perm_level: str):
    perm_level = perm_level.lower()
    if perm_level not in PERMISSIONS:
        return await ctx.send("❌ Niveau invalide ! (`perm1`, `perm2`, `perm3`, `perm_all`)")
    
    DATABASE["permissions"][member.id] = perm_level
    perm_data = PERMISSIONS[perm_level]
    
    embed = create_embed(
        "✅ Permission Ajoutée",
        f"**Membre:** {member.mention}\n**Niveau:** {perm_data['name']}\n\n"
        f"**Commandes:** " + ", ".join([f"`{cmd}`" for cmd in perm_data['commands']]),
        perm_data['color']
    )
    await ctx.send(embed=embed)

@bot.command(name='removeperm')
@is_owner_or_admin()
async def remove_perm(ctx, member: discord.Member):
    if member.id in DATABASE["permissions"]:
        del DATABASE["permissions"][member.id]
        await ctx.send(f"✅ Permissions retirées pour {member.mention}")
    else:
        await ctx.send(f"❌ {member.mention} n'a aucune permission !")

@bot.command(name='perms')
async def show_perms(ctx):
    embed = create_embed("📋 Système de Permissions", "Tous les niveaux disponibles :")
    for perm_key, perm_data in PERMISSIONS.items():
        commands_list = ", ".join([f"`{cmd}`" for cmd in perm_data['commands'][:5]])
        if len(perm_data['commands']) > 5:
            commands_list += f" +{len(perm_data['commands']) - 5}"
        embed.add_field(name=f"{perm_data['name']}", value=commands_list, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='myperm')
async def my_perm(ctx):
    user_perm = DATABASE["permissions"].get(ctx.author.id)
    if ctx.author.guild_permissions.administrator:
        embed = create_embed("👑 Vos Permissions", "**Niveau:** Administrateur\n**Accès:** Toutes les commandes", 0xf1c40f)
    elif user_perm:
        perm_data = PERMISSIONS[user_perm]
        embed = create_embed(
            "🔰 Vos Permissions",
            f"**Niveau:** {perm_data['name']}\n\n**Commandes:** " + ", ".join([f"`{cmd}`" for cmd in perm_data['commands']]),
            perm_data['color']
        )
    else:
        embed = create_embed("❌ Aucune Permission", "Vous n'avez pas de permissions personnalisées.", 0x95a5a6)
    await ctx.send(embed=embed)

@bot.command(name='warn')
@has_perm_level('warn')
async def warn(ctx, member: discord.Member, *, reason="Aucune raison"):
    if member.top_role >= ctx.author.top_role and ctx.author.id != CONFIG["owner_id"]:
        return await ctx.send("❌ Vous ne pouvez pas warn ce membre !")
    
    add_sanction(member.id, "warn", reason, str(ctx.author))
    warns = len([s for s in DATABASE["sanctions"].get(member.id, []) if s["type"] == "warn"])
    
    embed = create_embed(
        "⚠️ Avertissement",
        f"{member.mention} a été averti par {ctx.author.mention}\n\n"
        f"**Raison:** {reason}\n**Warns:** {warns}",
        0xFFA500
    )
    await ctx.send(embed=embed)
    
    log_embed = create_embed(
        "⚠️ Warn",
        f"**Membre:** {member.mention}\n**Modérateur:** {ctx.author.mention}\n"
        f"**Raison:** {reason}\n**Total:** {warns}",
        0xFFA500
    )
    await log_action(ctx.guild, "moderation", log_embed)
    
    try:
        await member.send(f"⚠️ Vous avez été averti sur **{ctx.guild.name}**\nRaison: {reason}")
    except:
        pass

@bot.command(name='mute')
@has_perm_level('mute')
async def mute(ctx, member: discord.Member, duration: int = 60, *, reason="Aucune raison"):
    if member.top_role >= ctx.author.top_role and ctx.author.id != CONFIG["owner_id"]:
        return await ctx.send("❌ Vous ne pouvez pas mute ce membre !")
    
    unmute_time = datetime.now() + timedelta(minutes=duration)
    DATABASE["mutes"][member.id] = unmute_time
    await member.timeout(unmute_time, reason=reason)
    add_sanction(member.id, "mute", reason, str(ctx.author))
    
    embed = create_embed(
        "🔇 Membre Mute",
        f"{member.mention} a été mute par {ctx.author.mention}\n\n"
        f"**Durée:** {duration} minutes\n**Raison:** {reason}",
        0xFF0000
    )
    await ctx.send(embed=embed)
    
    log_embed = create_embed(
        "🔇 Mute",
        f"**Membre:** {member.mention}\n**Modérateur:** {ctx.author.mention}\n"
        f"**Durée:** {duration}min\n**Raison:** {reason}",
        0xFF0000
    )
    await log_action(ctx.guild, "moderation", log_embed)

@bot.command(name='unmute')
@has_perm_level('mute')
async def unmute(ctx, member: discord.Member):
    if member.id not in DATABASE["mutes"]:
        return await ctx.send("❌ Ce membre n'est pas mute !")
    await member.timeout(None)
    del DATABASE["mutes"][member.id]
    embed = create_embed("🔊 Membre Unmute", f"{member.mention} a été unmute par {ctx.author.mention}", 0x00FF00)
    await ctx.send(embed=embed)

@bot.command(name='kick')
@has_perm_level('kick')
async def kick(ctx, member: discord.Member, *, reason="Aucune raison"):
    if member.top_role >= ctx.author.top_role and ctx.author.id != CONFIG["owner_id"]:
        return await ctx.send("❌ Vous ne pouvez pas kick ce membre !")
    
    add_sanction(member.id, "kick", reason, str(ctx.author))
    try:
        await member.send(f"👢 Vous avez été expulsé de **{ctx.guild.name}**\nRaison: {reason}")
    except:
        pass
    await member.kick(reason=reason)
    
    embed = create_embed("👢 Membre Expulsé", f"{member.mention} expulsé par {ctx.author.mention}\n**Raison:** {reason}", 0xFF0000)
    await ctx.send(embed=embed)
    
    log_embed = create_embed("👢 Kick", f"**Membre:** {member.mention}\n**Modérateur:** {ctx.author.mention}\n**Raison:** {reason}", 0xFF0000)
    await log_action(ctx.guild, "moderation", log_embed)

@bot.command(name='ban')
@has_perm_level('ban')
async def ban(ctx, member: discord.Member, *, reason="Aucune raison"):
    if member.top_role >= ctx.author.top_role and ctx.author.id != CONFIG["owner_id"]:
        return await ctx.send("❌ Vous ne pouvez pas ban ce membre !")
    
    add_sanction(member.id, "ban", reason, str(ctx.author))
    try:
        await member.send(f"🔨 Vous avez été banni de **{ctx.guild.name}**\nRaison: {reason}")
    except:
        pass
    await member.ban(reason=reason)
    
    embed = create_embed("🔨 Membre Banni", f"{member.mention} banni par {ctx.author.mention}\n**Raison:** {reason}", 0xFF0000)
    await ctx.send(embed=embed)
    
    log_embed = create_embed("🔨 Ban", f"**Membre:** {member.mention}\n**Modérateur:** {ctx.author.mention}\n**Raison:** {reason}", 0xFF0000)
    await log_action(ctx.guild, "moderation", log_embed)

@bot.command(name='clear')
@has_perm_level('clear')
async def clear(ctx, amount: int = 10):
    if amount > 100:
        return await ctx.send("❌ Maximum 100 messages !")
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"✅ {len(deleted) - 1} messages supprimés !")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name='sanctions')
async def sanctions(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author
    user_sanctions = DATABASE["sanctions"].get(member.id, [])
    if not user_sanctions:
        return await ctx.send(f"✅ {member.mention} n'a aucune sanction !")
    
    embed = create_embed(f"📋 Sanctions de {member.name}", f"Total: **{len(user_sanctions)}** sanctions")
    for i, sanction in enumerate(user_sanctions[-10:], 1):
        embed.add_field(
            name=f"{i}. {sanction['type'].upper()}",
            value=f"**Raison:** {sanction['reason']}\n**Par:** {sanction['moderator']}\n**Date:** {sanction['date']}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name='serverinfo')
async def server_info(ctx):
    """Affiche les infos du serveur GMod"""
    if not CONFIG["gmod_server"]["enabled"]:
        return await ctx.send("❌ Le système de serveur GMod n'est pas activé !")
    
    server_info = query_gmod_server(
        CONFIG["gmod_server"]["ip"],
        CONFIG["gmod_server"]["port"]
    )
    
    if server_info:
        embed = create_embed(
            f"🎮 {CONFIG['gmod_server']['name']}",
            f"**Statut:** 🟢 En ligne\n"
            f"**IP:** `{CONFIG['gmod_server']['ip']}:{CONFIG['gmod_server']['port']}`\n"
            f"**Joueurs:** {server_info['players']}/{server_info['max_players']}\n"
            f"**Nom réel:** {server_info['name']}",
            0x2ecc71
        )
        
        percentage = (server_info['players'] / server_info['max_players']) * 100 if server_info['max_players'] > 0 else 0
        filled = int(percentage / 10)
        bar = "🟩" * filled + "⬜" * (10 - filled)
        embed.add_field(name="Occupation", value=f"{bar} {percentage:.0f}%", inline=False)
        
    else:
        embed = create_embed(
            f"🎮 {CONFIG['gmod_server']['name']}",
            f"**Statut:** 🔴 Hors ligne\n"
            f"**IP:** `{CONFIG['gmod_server']['ip']}:{CONFIG['gmod_server']['port']}`\n"
            f"Le serveur ne répond pas actuellement.",
            0xe74c3c
        )
    
    await ctx.send(embed=embed)

@bot.command(name='setgmod')
@is_owner_or_admin()
async def set_gmod(ctx, ip: str, port: int, *, name: str):
    """Configure le serveur GMod"""
    CONFIG["gmod_server"]["ip"] = ip
    CONFIG["gmod_server"]["port"] = port
    CONFIG["gmod_server"]["name"] = name
    CONFIG["gmod_server"]["enabled"] = True
    
    server_info = query_gmod_server(ip, port)
    
    if server_info:
        embed = create_embed(
            "✅ Serveur GMod Configuré",
            f"**Nom:** {name}\n**IP:** `{ip}:{port}`\n"
            f"**Statut:** 🟢 En ligne\n**Joueurs:** {server_info['players']}/{server_info['max_players']}",
            0x2ecc71
        )
        if not update_gmod_status.is_running():
            update_gmod_status.start()
        else:
            update_gmod_status.restart()
    else:
        embed = create_embed(
            "⚠️ Serveur Configuré (Hors ligne)",
            f"**Nom:** {name}\n**IP:** `{ip}:{port}`\n"
            f"Le serveur a été configuré mais ne répond pas.",
            0xf39c12
        )
    
    await ctx.send(embed=embed)

@bot.command(name='togglegmod')
@is_owner_or_admin()
async def toggle_gmod(ctx):
    """Active/désactive le système GMod"""
    CONFIG["gmod_server"]["enabled"] = not CONFIG["gmod_server"]["enabled"]
    
    if CONFIG["gmod_server"]["enabled"]:
        update_gmod_status.start()
        await ctx.send("✅ Système GMod **activé** !")
    else:
        update_gmod_status.cancel()
        await bot.change_presence(activity=discord.Game(name=f"{CONFIG['prefix']}help"))
        await ctx.send("❌ Système GMod **désactivé** !")

@bot.command(name='refreshstatus')
@is_owner_or_admin()
async def refresh_status(ctx):
    """Force la mise à jour du statut"""
    if CONFIG["gmod_server"]["enabled"]:
        await update_gmod_status()
        await ctx.send("🔄 Statut mis à jour !")
    else:
        await ctx.send("❌ Le système GMod n'est pas activé !")

@bot.command(name='setupgmod')
@is_owner_or_admin()
async def setup_gmod_embed(ctx):
    """Crée un embed auto-actualisé du serveur GMod dans ce salon"""
    if not CONFIG["gmod_server"]["enabled"]:
        return await ctx.send("❌ Le système GMod n'est pas activé !")
    
    server_info = query_gmod_server(
        CONFIG["gmod_server"]["ip"],
        CONFIG["gmod_server"]["port"]
    )
    
    if server_info:
        embed = discord.Embed(
            title=f"🎮 {CONFIG['gmod_server']['name']}",
            description=f"**IP:** `{CONFIG['gmod_server']['ip']}:{CONFIG['gmod_server']['port']}`",
            color=0x2ecc71,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="📊 Statut", value="🟢 En ligne", inline=True)
        embed.add_field(name="👥 Joueurs", value=f"{server_info['players']}/{server_info['max_players']}", inline=True)
        embed.add_field(name="📡 Ping", value="✅ Actif", inline=True)
        
        percentage = (server_info['players'] / server_info['max_players']) * 100 if server_info['max_players'] > 0 else 0
        filled = int(percentage / 10)
        bar = "🟩" * filled + "⬜" * (10 - filled)
        embed.add_field(name="📈 Occupation", value=f"{bar}\n`{percentage:.1f}%`", inline=False)
        
        embed.set_footer(text=f"Mise à jour automatique toutes les 30s • {CONFIG['name']}")
        
    else:
        embed = discord.Embed(
            title=f"🎮 {CONFIG['gmod_server']['name']}",
            description=f"**IP:** `{CONFIG['gmod_server']['ip']}:{CONFIG['gmod_server']['port']}`",
            color=0xe74c3c,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="📊 Statut", value="🔴 Hors ligne", inline=True)
        embed.add_field(name="👥 Joueurs", value="0/0", inline=True)
        embed.add_field(name="📡 Ping", value="❌ Inactif", inline=True)
        
        embed.add_field(name="⚠️ Information", value="Le serveur ne répond pas actuellement.", inline=False)
        
        embed.set_footer(text=f"Mise à jour automatique toutes les 30s • {CONFIG['name']}")
    
    message = await ctx.send(embed=embed)
    
    DATABASE["config"]["gmod_embed_message_id"] = message.id
    DATABASE["config"]["gmod_embed_channel_id"] = ctx.channel.id
    
    await ctx.send(f"✅ Embed GMod créé ! Il se mettra à jour automatiquement toutes les **30 secondes**.", delete_after=10)

@bot.command(name='help')
async def help_command(ctx):
    embed = create_embed("📚 Menu d'aide", "Toutes les commandes disponibles :")
    embed.add_field(name="🛡️ Modération", value="`warn` `mute` `unmute` `kick` `ban` `clear` `sanctions`", inline=False)
    embed.add_field(name="🎫 Tickets", value="`setupticket`", inline=False)
    embed.add_field(name="🎉 Giveaways", value="`gstart` `gend` `greroll`", inline=False)
    embed.add_field(name="🔑 Permissions", value="`addperm` `removeperm` `perms` `myperm`", inline=False)
    embed.add_field(name="🎮 Serveur GMod", value="`serverinfo` `setupgmod` `setgmod` `togglegmod` `refreshstatus`", inline=False)
    embed.add_field(name="⚙️ Config", value="`logs` `config` `setprefix` `setwelcome`", inline=False)
    embed.add_field(name="🔧 Utils", value="`snipe` `discordinfo` `userinfo`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='snipe')
async def snipe(ctx):
    snipe_data = DATABASE["snipe"].get(ctx.channel.id)
    if not snipe_data:
        return await ctx.send("❌ Aucun message supprimé récemment !")
    time_ago = (datetime.now() - snipe_data["time"]).seconds
    embed = create_embed("🎯 Message Supprimé", f"**Auteur:** {snipe_data['author']}\n**Contenu:** {snipe_data['content']}\n**Il y a:** {time_ago}s")
    await ctx.send(embed=embed)

@bot.command(name='discordinfo')
async def discord_info(ctx):
    guild = ctx.guild
    embed = create_embed(f"📊 {guild.name}", f"Créé le {guild.created_at.strftime('%d/%m/%Y')}")
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="👑 Propriétaire", value=guild.owner.mention, inline=True)
    embed.add_field(name="👥 Membres", value=guild.member_count, inline=True)
    embed.add_field(name="💬 Salons", value=len(guild.channels), inline=True)
    await ctx.send(embed=embed)

@bot.command(name='userinfo')
async def userinfo(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author
    embed = create_embed(f"👤 {member.name}", f"ID: `{member.id}`")
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="📛 Pseudo", value=member.display_name, inline=True)
    embed.add_field(name="🎨 Rôle", value=member.top_role.mention, inline=True)
    embed.add_field(name="📅 Créé", value=member.created_at.strftime('%d/%m/%Y'), inline=True)
    embed.add_field(name="📥 Rejoint", value=member.joined_at.strftime('%d/%m/%Y'), inline=True)
    await ctx.send(embed=embed)

@bot.command(name='config')
@is_owner_or_admin()
async def config(ctx):
    embed = create_embed("⚙️ Configuration", "État du bot")
    embed.add_field(name="Préfixe", value=f"`{CONFIG['prefix']}`", inline=True)
    embed.add_field(name="Tickets actifs", value=str(len(DATABASE["tickets"])), inline=True)
    embed.add_field(name="Giveaways", value=str(len(DATABASE["giveaways"])), inline=True)
    await ctx.send(embed=embed)

@bot.command(name='setprefix')
@is_owner_or_admin()
async def setprefix(ctx, prefix: str):
    CONFIG["prefix"] = prefix
    bot.command_prefix = prefix
    await ctx.send(f"✅ Préfixe changé en `{prefix}`")

@bot.command(name='setwelcome')
@is_owner_or_admin()
async def setwelcome(ctx, channel: discord.TextChannel):
    DATABASE["config"]["welcome_channel"] = channel.id
    await ctx.send(f"✅ Salon de bienvenue : {channel.mention}")

@bot.event
async def on_ready():
    print(f'✅ {bot.user} connecté !')
    print(f'📊 {len(bot.guilds)} serveur(s)')
    print(f'👥 {sum(g.member_count for g in bot.guilds)} utilisateurs')
    
    check_giveaways.start()
    
    if CONFIG["gmod_server"]["enabled"]:
        print(f'🎮 Surveillance GMod activée : {CONFIG["gmod_server"]["name"]}')
        print(f'⏱️  Mise à jour toutes les 30 secondes')
        update_gmod_status.start()
    else:
        await bot.change_presence(activity=discord.Game(name=f"{CONFIG['prefix']}help"))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Permissions insuffisantes !")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Niveau de permission requis manquant !")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument manquant ! `{CONFIG['prefix']}help`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Erreur: {error}")

if __name__ == "__main__":
    print("🚀 Démarrage du bot...")
    print("📦 Chargement des modules...")
    keep_alive()
    bot.run(CONFIG["token"])