"""Games bot features."""

from bot_state import (
    Image, ImageDraw, ImageOps, app_commands, asyncio,
    bot, discord, fit_text, io, load_card_font,
    math, random, wrap_card_text,
)


def render_game_card(game, headline, detail, avatar_bytes=None):
    width, height = 1280, 720
    accents = {
        "coin": (255, 189, 89), "dice": (101, 217, 185), "8ball": (169, 139, 255),
        "rps": (255, 111, 145), "rpsls": (255, 111, 145), "highlow": (96, 188, 255),
        "number": (255, 146, 95), "math": (119, 211, 255), "wyr": (255, 133, 204),
        "choose": (119, 224, 169),
    }
    accent = accents.get(game, (148, 132, 255))
    pale = tuple(255 - (255 - component) // 7 for component in accent)
    image = Image.new("RGB", (width, height), (249, 248, 243))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        amount = y / height
        color = (int(255 - 8 * amount), int(252 - 5 * amount), int(242 + 10 * amount))
        draw.line((0, y, width, y), fill=color)
    draw.ellipse((900, -250, 1430, 280), fill=pale)
    draw.ellipse((-210, 550, 190, 950), fill=(241, 244, 255))
    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=38, fill=(255, 255, 255), outline=(232, 231, 224), width=2)
    draw.rounded_rectangle((25, 25, width - 25, 185), radius=36, fill=(255, 255, 255))
    draw.rectangle((25, 140, width - 25, 185), fill=(255, 255, 255))
    small = load_card_font(16, bold=True)
    title_font = load_card_font(30, bold=True)
    hero_font = load_card_font(66, bold=True)
    detail_font = load_card_font(27)
    dark = (39, 45, 65)
    muted = (104, 113, 134)
    draw.rounded_rectangle((62, 57, 183, 94), radius=18, fill=accent)
    draw.text((79, 67), "ARCADE", font=small, fill=(255, 255, 255))
    display_game = game.replace("8ball", "MAGIC 8-BALL").replace("rpsls", "RPSLS").replace("rps", "ROCK PAPER SCISSORS").replace("wyr", "WOULD YOU RATHER").upper()
    draw.text((62, 117), fit_text(draw, display_game, title_font, 740), font=title_font, fill=muted)
    draw.rounded_rectangle((62, 236, 75, 510), radius=7, fill=accent)
    wrapped_headline = wrap_card_text(draw, headline, hero_font, 710, max_lines=2)
    for index, line in enumerate(wrapped_headline):
        draw.text((105, 239 + index * 82), line, font=hero_font, fill=dark)
    detail_lines = wrap_card_text(draw, detail.replace("\n", " · "), detail_font, 690, max_lines=2)
    for index, line in enumerate(detail_lines):
        draw.text((107, 432 + index * 39), line, font=detail_font, fill=muted)

    # A bright illustration panel with art tailored to the selected mini-game.
    panel = (840, 218, 1197, 578)
    draw.rounded_rectangle(panel, radius=34, fill=pale)
    cx, cy = 1018, 398
    if game == "coin":
        # Gold coin face explicitly displays the side returned by the flip.
        draw.ellipse((cx - 113, cy - 101, cx + 113, cy + 125), fill=(221, 159, 43))
        draw.ellipse((cx - 111, cy - 112, cx + 111, cy + 110), fill=(255, 195, 54), outline=(221, 145, 27), width=8)
        draw.ellipse((cx - 91, cy - 92, cx + 91, cy + 91), outline=(255, 229, 126), width=5)
        # A simple embossed star gives the coin a readable emblem without emoji fonts.
        star_points = []
        for point in range(10):
            radius = 25 if point % 2 == 0 else 11
            angle = -math.pi / 2 + point * math.pi / 5
            star_points.append((cx + math.cos(angle) * radius, cy - 34 + math.sin(angle) * radius))
        draw.polygon(star_points, fill=(255, 236, 158))
        coin_label = "HEADS" if headline.lower().startswith("heads") else "TAILS"
        coin_font = load_card_font(25, bold=True)
        label_w = draw.textlength(coin_label, font=coin_font)
        draw.text((cx - label_w / 2, cy + 17), coin_label, font=coin_font, fill=(120, 75, 13))
    elif game == "dice":
        import re
        rolled = re.search(r"rolled (\d+)", headline, re.IGNORECASE)
        value = int(rolled.group(1)) if rolled else random.randint(1, 6)
        die = (cx - 88, cy - 88, cx + 88, cy + 88)
        draw.rounded_rectangle((die[0] + 9, die[1] + 12, die[2] + 9, die[3] + 12), radius=30, fill=(202, 89, 83))
        draw.rounded_rectangle(die, radius=30, fill=(255, 255, 255), outline=(225, 225, 231), width=3)
        pip_positions = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)],
                         4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
                         5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
                         6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}
        if value <= 6:
            for px, py in pip_positions[value]:
                x, y = cx + px * 48, cy + py * 48
                draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=(244, 91, 91))
        else:
            value_font = load_card_font(64, bold=True)
            text = str(value)
            draw.text((cx - draw.textlength(text, font=value_font) / 2, cy - 43), text, font=value_font, fill=(244, 91, 91))
    elif game == "8ball":
        draw.ellipse((cx - 113, cy - 113, cx + 113, cy + 113), fill=(34, 39, 56), outline=(21, 25, 37), width=5)
        draw.ellipse((cx - 65, cy - 65, cx + 65, cy + 65), fill=(255, 255, 255))
        text = "8"
        font = load_card_font(78, bold=True)
        draw.text((cx - draw.textlength(text, font=font) / 2, cy - 54), text, font=font, fill=(34, 39, 56))
    elif game in {"rps", "rpsls"}:
        for index, (label, color) in enumerate((("R", (255, 107, 107)), ("P", (80, 164, 255)), ("S", (117, 203, 135)))):
            x = 900 + index * 93
            draw.rounded_rectangle((x, 315, x + 76, 410), radius=22, fill=color)
            font = load_card_font(42, bold=True)
            draw.text((x + 38 - draw.textlength(label, font=font) / 2, 332), label, font=font, fill=(255, 255, 255))
            draw.text((x + 38 - draw.textlength(label, font=small) / 2, 430), label, font=small, fill=dark)
        draw.text((915, 484), "ROCK     PAPER     SCISSORS", font=load_card_font(12, bold=True), fill=muted)
    elif game == "highlow":
        import re
        cards = re.search(r"First card: (\d+) · next card: (\d+)", detail)
        values = cards.groups() if cards else ("7", "K")
        for index, value in enumerate(values):
            x = 907 + index * 112
            color = (232, 71, 87) if index else (46, 56, 76)
            draw.rounded_rectangle((x + 5, 300, x + 96, 493), radius=16, fill=(217, 216, 210))
            draw.rounded_rectangle((x, 292, x + 91, 485), radius=16, fill=(255, 255, 255), outline=(225, 226, 231), width=2)
            font = load_card_font(36, bold=True)
            draw.text((x + 16, 307), value, font=font, fill=color)
            draw.text((x + 19, 365), "♥" if color[0] > 150 else "♠", font=load_card_font(39, bold=True), fill=color)
    elif game == "number":
        import re
        match = re.search(r"number: (\d+)", detail)
        number = match.group(1) if match else "?"
        draw.ellipse((cx - 112, cy - 112, cx + 112, cy + 112), fill=(255, 143, 95))
        draw.ellipse((cx - 92, cy - 94, cx + 92, cy + 90), fill=(255, 174, 129))
        font = load_card_font(86, bold=True)
        draw.text((cx - draw.textlength(number, font=font) / 2, cy - 60), number, font=font, fill=(255, 255, 255))
    elif game == "math":
        draw.rounded_rectangle((900, 302, 1136, 481), radius=28, fill=(255, 255, 255), outline=(218, 231, 242), width=3)
        equation_font = load_card_font(38, bold=True)
        equation = fit_text(draw, headline.replace("?", "?"), equation_font, 200)
        draw.text((cx - draw.textlength(equation, font=equation_font) / 2, 365), equation, font=equation_font, fill=(62, 153, 224))
    elif game == "wyr":
        for index, (label, color) in enumerate((("A", (255, 133, 204)), ("B", (130, 125, 255)))):
            x = 900 + index * 120
            draw.rounded_rectangle((x, 300, x + 105, 490), radius=25, fill=color)
            font = load_card_font(66, bold=True)
            draw.text((x + 52 - draw.textlength(label, font=font) / 2, 350), label, font=font, fill=(255, 255, 255))
    else:
        star_points = []
        for point in range(10):
            radius = 118 if point % 2 == 0 else 55
            angle = -math.pi / 2 + point * math.pi / 5
            star_points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
        draw.polygon(star_points, fill=(255, 200, 66), outline=(238, 154, 28))
        draw.text((cx - 13, cy - 25), "!", font=load_card_font(60, bold=True), fill=(255, 255, 255))

    draw.text((62, 615), "PLAY AGAIN ANYTIME  ·  GOOD LUCK", font=small, fill=muted)
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = ImageOps.fit(avatar, (42, 42))
            mask = Image.new("L", (42, 42), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 41, 41), fill=255)
            image.paste(avatar, (62, 652), mask)
            draw.ellipse((60, 650, 104, 694), outline=accent, width=2)
            draw.text((117, 665), "PLAYER RESULT CARD", font=small, fill=muted)
        except Exception:
            pass
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()

class MathAnswerView(discord.ui.View):
    def __init__(self, player_id, answer, options):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.answer = answer
        for option in options:
            button = discord.ui.Button(label=str(option), style=discord.ButtonStyle.secondary)
            button.callback = self.make_callback(option)
            self.add_item(button)

    def make_callback(self, option):
        async def callback(interaction):
            if interaction.user.id != self.player_id:
                await interaction.response.send_message("This round belongs to someone else.", ephemeral=True)
                return
            embed = interaction.message.embeds[0]
            embed.title = "Correct!" if option == self.answer else "Not quite!"
            embed.description = f"You chose **{option}**. The answer was **{self.answer}**."
            embed.color = discord.Color.green() if option == self.answer else discord.Color.red()
            await interaction.response.edit_message(embed=embed, view=None)
        return callback

class DuelInviteView(discord.ui.View):
    def __init__(self, challenger, opponent, game):
        super().__init__(timeout=120)
        self.challenger = challenger
        self.opponent = opponent
        self.game = game

    async def interaction_check(self, interaction):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message(
                f"Only {self.opponent.mention} can answer this challenge.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Accept", emoji="🎮", style=discord.ButtonStyle.success)
    async def accept(self, interaction, button):
        if self.game == "tictactoe":
            view = TicTacToeView(self.challenger, self.opponent)
            embed = view.make_embed("It’s your turn, " + self.challenger.display_name + "!")
        else:
            view = RockPaperScissorsView(self.challenger, self.opponent)
            embed = view.make_embed()
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = interaction.message

    @discord.ui.button(label="Decline", emoji="✋", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction, button):
        await interaction.response.edit_message(
            content=f"{self.opponent.mention} declined the challenge.", embed=None, view=None
        )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="Challenge expired.", view=self)
            except discord.HTTPException:
                pass

class TicTacToeView(discord.ui.View):
    WIN_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7),
                 (2, 5, 8), (0, 4, 8), (2, 4, 6))

    def __init__(self, player_x, player_o):
        super().__init__(timeout=600)
        self.players = {"❌": player_x, "⭕": player_o}
        self.board = [None] * 9
        self.turn = "❌"
        self.finished = False
        self.message = None
        for position in range(9):
            button = discord.ui.Button(label="▫️", style=discord.ButtonStyle.secondary,
                                       row=position // 3)
            button.callback = self.make_move_callback(position, button)
            self.add_item(button)

    def make_embed(self, status):
        cells = [mark or "▫️" for mark in self.board]
        board = "\n".join("　".join(cells[row:row + 3]) for row in (0, 3, 6))
        embed = discord.Embed(title="⭕ Tic-tac-toe", description=board,
                              color=discord.Color.from_rgb(119, 211, 255))
        embed.add_field(name="Players", value=f"❌ {self.players['❌'].mention}\n⭕ {self.players['⭕'].mention}", inline=True)
        embed.add_field(name="Turn", value=status, inline=True)
        return embed

    def make_move_callback(self, position, button):
        async def callback(interaction):
            if self.finished:
                await interaction.response.send_message("This game has ended.", ephemeral=True)
                return
            if interaction.user.id != self.players[self.turn].id:
                await interaction.response.send_message("It’s not your turn.", ephemeral=True)
                return
            if self.board[position]:
                await interaction.response.send_message("That square is already taken.", ephemeral=True)
                return
            mark = self.turn
            self.board[position] = mark
            button.label = mark
            button.emoji = None
            button.style = discord.ButtonStyle.danger if mark == "❌" else discord.ButtonStyle.primary
            button.disabled = True
            winner = None
            for line in self.WIN_LINES:
                if all(self.board[index] == mark for index in line):
                    winner = mark
                    break
            if winner:
                self.finished = True
                for child in self.children:
                    child.disabled = True
                embed = self.make_embed(f"🏆 {self.players[winner].mention} wins!")
                embed.color = discord.Color.green()
            elif all(self.board):
                self.finished = True
                for child in self.children:
                    child.disabled = True
                embed = self.make_embed("🤝 It’s a draw!")
            else:
                self.turn = "⭕" if mark == "❌" else "❌"
                embed = self.make_embed(f"{self.players[self.turn].mention}, your move!")
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="This game expired.", view=self)
            except discord.HTTPException:
                pass

class RockPaperScissorsView(discord.ui.View):
    MOVES = ("rock", "paper", "scissors")
    EMOJIS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

    def __init__(self, player_one, player_two):
        super().__init__(timeout=180)
        self.players = (player_one, player_two)
        self.choices = {}
        self.message = None
        for move, emoji in self.EMOJIS.items():
            button = discord.ui.Button(label=move.title(), emoji=emoji,
                                       style=discord.ButtonStyle.secondary)
            button.callback = self.make_choice_callback(move)
            self.add_item(button)

    def make_embed(self, status="Both players: choose your move (your choice stays hidden)."):
        embed = discord.Embed(title="✊ Rock, paper, scissors",
                              description=status, color=discord.Color.from_rgb(255, 111, 145))
        embed.add_field(name="Players", value=f"{self.players[0].mention} vs {self.players[1].mention}")
        return embed

    def make_choice_callback(self, move):
        async def callback(interaction):
            player_id = interaction.user.id
            if player_id not in {player.id for player in self.players}:
                await interaction.response.send_message("You aren’t playing this round.", ephemeral=True)
                return
            if player_id in self.choices:
                await interaction.response.send_message("Your move is already locked in.", ephemeral=True)
                return
            self.choices[player_id] = move
            if len(self.choices) < 2:
                await interaction.response.defer(ephemeral=True)
                await interaction.followup.send("Your move is locked in 🔒", ephemeral=True)
                await interaction.message.edit(embed=self.make_embed(
                    f"{interaction.user.mention} has locked in. Waiting for the other player…"), view=self)
                return

            first, second = self.players
            first_move, second_move = self.choices[first.id], self.choices[second.id]
            if first_move == second_move:
                result, color = "🤝 It’s a tie!", discord.Color.gold()
            elif (first_move, second_move) in (("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")):
                result, color = f"🏆 {first.mention} wins!", discord.Color.green()
            else:
                result, color = f"🏆 {second.mention} wins!", discord.Color.green()
            embed = self.make_embed(result)
            embed.add_field(name=first.display_name, value=self.EMOJIS[first_move], inline=True)
            embed.add_field(name=second.display_name, value=self.EMOJIS[second_move], inline=True)
            embed.color = color
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
        return callback

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="This round expired.", view=self)
            except discord.HTTPException:
                pass

@bot.hybrid_command(name="duel", description="Challenge someone to a two-player game")
@app_commands.describe(opponent="The server member you want to challenge", game="Pick a game")
@app_commands.choices(game=[
    app_commands.Choice(name="Tic-tac-toe", value="tictactoe"),
    app_commands.Choice(name="Rock paper scissors", value="rps"),
])
async def duel(ctx, opponent: discord.Member, game: str):
    if not ctx.guild:
        await ctx.send("Duel games can only be started in a server.")
        return
    if opponent.bot or opponent.id == ctx.author.id:
        await ctx.send("Choose another human server member to challenge.")
        return
    game_name = "tic-tac-toe" if game == "tictactoe" else "rock, paper, scissors"
    view = DuelInviteView(ctx.author, opponent, game)
    message = await ctx.send(
        f"🎮 {opponent.mention}, {ctx.author.mention} challenged you to **{game_name}**! "
        "Accept within 2 minutes to play.", view=view
    )
    view.message = message

@bot.hybrid_command(name="games", description="Play a game and get a custom result card")
@app_commands.describe(game="Choose a game", choice="Your pick or guess (varies by game)")
@app_commands.choices(game=[
    app_commands.Choice(name="Coin flip", value="coin"),
    app_commands.Choice(name="Dice roll", value="dice"),
    app_commands.Choice(name="Magic 8-ball", value="8ball"),
    app_commands.Choice(name="Rock paper scissors", value="rps"),
    app_commands.Choice(name="Rock paper scissors lizard Spock", value="rpsls"),
    app_commands.Choice(name="High or low", value="highlow"),
    app_commands.Choice(name="Number guess (1–10)", value="number"),
    app_commands.Choice(name="Quick math", value="math"),
    app_commands.Choice(name="Would you rather", value="wyr"),
    app_commands.Choice(name="Random picker", value="choose"),
])
async def games(ctx, game: str, choice: str = ""):
    # Acknowledge slash commands before validating inputs or rendering the card;
    # Discord expires unanswered interactions after a few seconds.
    await ctx.defer()
    headline, detail = "Game result", ""
    game_view = None
    reaction_choices = []
    if game == "coin":
        headline = random.choice(["Heads", "Tails"])
        detail = "The coin has spoken."
    elif game == "dice":
        sides = random.choice([6, 12, 20])
        headline = f"You rolled {random.randint(1, sides)}"
        detail = f"A d{sides} roll. Run it back for another one."
    elif game == "8ball":
        headline = random.choice(["Absolutely", "Ask again later", "The vibes say yes", "Not looking good", "It is certain", "Signs point to no"])
        detail = "The magic 8-ball has delivered its verdict."
    elif game in {"rps", "rpsls"}:
        moves = ["rock", "paper", "scissors"] if game == "rps" else ["rock", "paper", "scissors", "lizard", "spock"]
        if choice.lower() not in moves:
            await ctx.send(f"Pick one: {', '.join(moves)}")
            return
        bot_move = random.choice(moves)
        if choice.lower() == bot_move:
            outcome = "Tie game"
        else:
            defeats = {
                "rock": {"scissors", "lizard"}, "paper": {"rock", "spock"},
                "scissors": {"paper", "lizard"}, "lizard": {"paper", "spock"},
                "spock": {"rock", "scissors"},
            }
            outcome = "You win" if bot_move in defeats[choice.lower()] else "Bot wins"
        headline = outcome
        detail = f"You picked {choice.lower()} · bot picked {bot_move}"
    elif game == "highlow":
        first, second = random.randint(1, 13), random.randint(1, 13)
        if choice.lower() not in {"high", "low"}:
            await ctx.send("Choose **high** or **low** for your guess.")
            return
        won = (choice.lower() == "high" and second > first) or (choice.lower() == "low" and second < first)
        headline = "You got it!" if won else "Not this time"
        detail = f"First card: {first} · next card: {second} · you chose {choice.lower()}"
    elif game == "number":
        if not choice.isdigit() or not 1 <= int(choice) <= 10:
            await ctx.send("Guess a whole number from 1 to 10 in the choice field.")
            return
        answer = random.randint(1, 10)
        guess = int(choice)
        headline = "Bullseye!" if guess == answer else "Close one" if abs(guess - answer) <= 2 else "Missed it"
        detail = f"Your guess: {guess} · number: {answer}"
    elif game == "math":
        left, right = random.randint(2, 18), random.randint(2, 18)
        operation = random.choice(["+", "−", "×"])
        answer = left + right if operation == "+" else left - right if operation == "−" else left * right
        headline = f"{left} {operation} {right} = ?"
        detail = "Choose the answer below."
        answers = {answer}
        while len(answers) < 4:
            answers.add(answer + random.choice([i for i in range(-8, 9) if i != 0]))
        answer_options = list(answers)
        random.shuffle(answer_options)
        game_view = MathAnswerView(ctx.author.id, answer, answer_options)
    elif game == "wyr":
        options = random.choice([
            ("Speak every language", "Talk to animals"),
            ("Explore space", "Explore the deep sea"),
            ("Always be early", "Always have perfect timing"),
        ])
        picked = "A" if choice.lower() in {"a", "1"} else "B" if choice.lower() in {"b", "2"} else ""
        if not picked:
            headline = "Choose your side"
            reaction_choices = ["🅰️", "🅱️"]
        else:
            headline = f"You chose {picked}"
        detail = f"A: {options[0]} · B: {options[1]}"
    elif game == "choose":
        options = [item.strip() for item in choice.split(",") if item.strip()]
        if len(options) < 2:
            await ctx.send("Give me at least two comma-separated options in the choice field.")
            return
        headline = random.choice(options)[:42]
        detail = f"Picked from {len(options)} options"

    avatar = None
    try:
        avatar = await ctx.author.display_avatar.read()
    except discord.HTTPException:
        pass
    image_bytes = await asyncio.to_thread(render_game_card, game, headline, detail, avatar)
    file = discord.File(io.BytesIO(image_bytes), filename="game-result.png")
    embed = discord.Embed(title=f"{ctx.author.display_name} · {game}", description=detail, color=discord.Color.blurple())
    embed.set_image(url="attachment://game-result.png")
    message = await ctx.send(embed=embed, file=file, view=game_view)
    for emoji in reaction_choices:
        await message.add_reaction(emoji)
