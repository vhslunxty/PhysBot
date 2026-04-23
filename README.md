# 🤖 PhysBot

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Library](https://img.shields.io/badge/library-discord.py-orange)](https://discordpy.readthedocs.io/)

**PhysBot** est un bot Discord multifonction conçu pour la gestion de serveurs communautaires et l'intégration en temps réel de serveurs de jeu **Garry's Mod**.

---

### 🌟 Fonctionnalités principales

* **📊 Monitoring GMod :** Affiche le nombre de joueurs, la map et le statut du serveur en temps réel via le protocole Source.
* **🛡️ Modération complète :** Système de sanctions incluant `warn`, `mute`, `kick`, `ban` et `clear` avec historique.
* **🎫 Système de Tickets :** Gestion des demandes (Assistance, RP, Staff) via des boutons interactifs.
* **🔑 Permissions par niveaux :** 4 paliers de permissions personnalisés (Junior, Modérateur, Senior, Admin).
* **🎉 Giveaways :** Module de création de concours avec tirage au sort automatique et système de reroll.
* **📝 Logs avancés :** Surveillance automatique des messages supprimés/édités et des mouvements de membres.

---

### 🚀 Guide d'installation

1.  **Prérequis :**
    Assurez-vous d'avoir Python installé. Installez ensuite la dépendance nécessaire :
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration du fichier `bot.py` :**
    Modifiez la section `CONFIG` au début du script :
    * `token` : Votre token secret Discord.
    * `owner_id` : Votre ID Discord pour les droits administrateur.
    * `gmod_server` : L'IP et le Port de votre serveur GMod.

3.  **Lancement :**
    ```bash
    python bot.py
    ```

---

### ⚙️ Initialisation du serveur

Une fois le bot en ligne, utilisez ces commandes pour configurer vos salons :
* **`+logs`** : Crée automatiquement la catégorie et les salons de logs.
* **`+setupticket`** : Envoie le menu interactif pour l'ouverture des tickets.
* **`+setupgmod`** : Affiche l'embed d'état du serveur GMod (actualisé toutes les 30s).

---

### 📂 Structure du projet
* `bot.py` : Le code source principal du bot.
* `requirements.txt` : Liste des dépendances (discord.py).
* `keep_alive.py` : Script pour maintenir le bot actif 24/7.
* `.gitignore` : Pour éviter d'envoyer les fichiers temporaires sur GitHub.

---

> **⚠️ AVERTISSEMENT SÉCURITÉ :** Ne partagez jamais votre fichier `bot.py` sans avoir effacé votre **Token Discord**. Si votre token est publié, n'importe qui pourra prendre le contrôle de votre bot.
