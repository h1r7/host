import discord
from discord.ext import commands
import json
import asyncio

from cryptography.fernet import Fernet

# 고정된 키 사용
key = b'zsS8Jk5lI9ebXn5A7PzZvGR_pBqDh4Uy13Zkq9RvEsg='  # 생성된 키를 그대로 사용
cipher_suite = Fernet(key)

# 데이터 암호화
def encrypt_data(data: str) -> str:
    return cipher_suite.encrypt(data.encode()).decode()

# 데이터 복호화
def decrypt_data(data: str) -> str:
    return cipher_suite.decrypt(data.encode()).decode()

# 봇 인스턴스 생성
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True  # 유저 관련 이벤트 처리 가능하게

bot = commands.Bot(command_prefix="!", intents=intents)

# 관리자 ID
admin_user_id = 1071962941055832166

# 인증 채널 및 역할 ID
verification_channel_id = 1281985460759171102  # 인증 메시지를 보낼 채널 ID
verification_role_id = 1281984545079427234  # 부여할 역할 ID

# 유저 정보 저장 (유저 ID를 기준으로 구매 금액 및 보유 금액 설정)
user_data = {}

# 환영 메시지를 보낼 채널 ID
welcome_channel_id = 1281486623795707937  # 환영 메시지를 보낼 채널 ID로 변경
test_channel_id = 1281599070800187416
admin_channel_id = 1281906818116751370
log_channel_id = 1283739021746638930  # 로그 채널

# 제품 및 재고 정보
product_data = {
    "유튜브 프리미엄": {
        "유튜브 프리미엄 6개월": {"price": 15000, "stock": 10},
        "유튜브 프리미엄 12개월": {"price": 25000, "stock": 10},
    },
    "디스코드 니트로": {
        "디스코드 니트로 12개월 ": {"price": 25000, "stock": 0},
    },
    "넷플릭스": {
        "넷플릭스 무제한": {"price": 5000, "stock": 0},
    },
    "스포티파이": {
        "스포티파이 무제한": {"price": 3000, "stock": 0},
    }
}   

# 사용자가 열고 있는 문의, 충전, 구매 채널을 저장 (사용자 ID를 기준으로)
active_channels = {
    "inquiry": {},  # 문의 채널
    "charge": {},   # 충전 채널
    "purchase": {}  # 구매 채널
}

def get_user_grade(purchase_amount):
    if purchase_amount >= 1000000:
        return "vip"
    elif purchase_amount >= 500000:
        return "level 5"
    elif purchase_amount >= 100000:
        return "level 4"
    elif purchase_amount >= 50000:
        return "level 3"
    elif purchase_amount >= 10000:
        return "level 2"
    else:
        return "level 1 (일반 등급)"
    
async def log_data_periodically():
    while True:
        # 1분마다 로그 채널에 데이터 출력
        await asyncio.sleep(3600)  # 60초 대기
        log_channel = bot.get_channel(log_channel_id)

        if log_channel is not None:
            # user_data와 product_data를 암호화하여 출력
            combined_data = {
                "user_data": user_data,
                "product_data": product_data
            }
            output_message = json.dumps(combined_data, ensure_ascii=False)
            encrypted_output = encrypt_data(output_message)

            # 메시지를 깔끔하게 Embed 형태로 전송
            embed = discord.Embed(
                title="🔒 주기적인 데이터 로그",
                description=f"```{encrypted_output}```",
                color=discord.Color.blue()
            )
            embed.set_footer(text="주기적인 데이터 출력")

            await log_channel.send(embed=embed)

# 문의 채널 생성 및 로그 남기기
async def create_support_channel(interaction: discord.Interaction):
    user = interaction.user

    # 이미 문의 채널이 열려 있는지 확인
    if user.id in active_channels["inquiry"]:
        await interaction.response.send_message("이미 처리 중인 문의가 있습니다.", ephemeral=True)
        return

    guild = interaction.guild
    user = interaction.user
    category = discord.utils.get(guild.categories, name="Support")

    if not category:
        category = await guild.create_category(name="Support")

    # 유저에게만 보이는 채널 생성
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True),
        guild.get_member(admin_user_id): discord.PermissionOverwrite(read_messages=True)
    }

    channel_name = f"{user.display_name}-문의"
    new_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

    # 새로운 채널에 메시지 전송
    view = InquiryCloseView(new_channel)

    # 박스 형태로 예쁘게 꾸미기
    embed = discord.Embed(
        title="📩 문의 접수",
        description=(
            "궁금한 사항을 남겨주세요, 빠른 시일 내에 답변드리겠습니다.\n\n"
            "```yaml\n"
            "관리자가 확인 중입니다. 조금만 기다려주세요.\n"
            "```"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="문의 채널을 닫으려면 '문의닫기' 버튼을 눌러주세요.")

    # 관리자 호출 멘션
    await new_channel.send(content=f"<@&1281612006205554770>", embed=embed, view=view)

    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        log_embed = discord.Embed(
            title="🔔 문의 채널 생성",
            description=f"유저:{user.mention}.: {new_channel.mention}",
            color=discord.Color.green()
        )
        await log_channel.send(embed=log_embed)
    # 사용자에게 알림
    active_channels["inquiry"][user.id] = new_channel
    await interaction.response.send_message(f"{user.mention}, 새로운 문의 채널이 열렸습니다: {new_channel.mention}", ephemeral=True)

# 채널 닫기 시 로그 남기기
class InquiryCloseView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="문의닫기", style=discord.ButtonStyle.danger)
    async def close_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = InquiryCloseConfirmView(self.channel)
        await interaction.response.send_message("정말로 이 채널을 닫으시겠습니까?", view=view, ephemeral=True)

# 채널 닫기 확인 View
class InquiryCloseConfirmView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=30)
        self.channel = channel

    @discord.ui.button(label="네", style=discord.ButtonStyle.danger)
    async def confirm_close_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await close_channel(self.channel, interaction)

async def close_channel(channel, interaction):
    # 채널 닫을 때 active_channels에서 제거
    user_id = interaction.user.id
    if user_id in active_channels["inquiry"]:
        del active_channels["inquiry"][user_id]
    elif user_id in active_channels["charge"]:
        del active_channels["charge"][user_id]
    elif user_id in active_channels["purchase"]:
        del active_channels["purchase"][user_id]
    overwrites = {
        channel.guild.default_role: discord.PermissionOverwrite(read_messages=False)
    }
    await channel.edit(overwrites=overwrites, name=f"closed-{channel.name}")

    # 로그 채널에 메시지 전송
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        log_embed = discord.Embed(
            title="🚪 채널 삭제 예정",
            description=f"채널: {channel.name} (삭제 예정)",
            color=discord.Color.red()
        )
        await log_channel.send(embed=log_embed)

    # 1분 후에 채널 삭제
    await asyncio.sleep(60)
    await channel.delete()

    if log_channel:
        log_embed = discord.Embed(
            title="❌ 완전 삭제",
            description=f"채널: {channel.name}",
            color=discord.Color.red()
        )
        await log_channel.send(embed=log_embed)

# 충전 채널 생성 및 로그 남기기
async def create_charge_channel(depositor_name: str, amount: int, interaction: discord.Interaction):
    user = interaction.user

    # 이미 충전 채널이 열려 있는지 확인
    if user.id in active_channels["charge"]:
        await interaction.response.send_message("이미 처리 중인 충전 요청이 있습니다.", ephemeral=True)
        return
    guild = interaction.guild
    user = interaction.user
    category = discord.utils.get(guild.categories, name="Charge")

    if not category:
        category = await guild.create_category(name="Charge")

    # 유저에게만 보이는 채널 생성
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True),
        guild.get_member(admin_user_id): discord.PermissionOverwrite(read_messages=True)
    }

    channel_name = f"{depositor_name}-{amount}"
    new_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

    # 박스 형태로 메시지 꾸미기
    embed = discord.Embed(
        title="💰 충전 요청 접수",
        description=(
            f"**입금자명:** {depositor_name}\n"
            f"**금액:** {amount:,}원\n\n"
            "```yaml\n"
            "계좌 정보: [1001-3056-9166 (토스뱅크 / ㄱㅈㅎ)]\n"
            "입금 후 이중창 화면 캡처를 첨부 부탁드립니다.\n"
            "```"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="충전 완료 후 '충전완료' 버튼을 눌러주세요.")
    active_channels["charge"][user.id] = new_channel
    await interaction.response.send_message(f"{user.mention}, 새로운 충전 채널이 열렸습니다: {new_channel.mention}", ephemeral=True)

    # 관리자 호출 멘션
    view = ChargeCloseView(new_channel, user.id, amount)
    await new_channel.send(content=f"<@&1281612006205554770>", embed=embed, view=view)

    # 로그 채널에 메시지 전송
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        log_embed = discord.Embed(
            title="🔔 충전 채널 생성",
            description=f"입금자명: {depositor_name}\n금액: {amount}원\n채널: {new_channel.mention}",
            color=discord.Color.green()
        )
        await log_channel.send(embed=log_embed)

# 충전 완료 및 닫기 기능 추가
class ChargeCloseView(discord.ui.View):
    def __init__(self, channel, user_id, amount):
        super().__init__(timeout=None)
        self.channel = channel
        self.user_id = user_id
        self.amount = amount

    @discord.ui.button(label="문의닫기", style=discord.ButtonStyle.danger)
    async def close_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = InquiryCloseConfirmView(self.channel)
        await interaction.response.send_message("정말로 이 채널을 닫으시겠습니까?", view=view, ephemeral=True)

    @discord.ui.button(label="충전완료", style=discord.ButtonStyle.success)
    async def charge_complete_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == admin_user_id:
            # 보유 금액 증가
            user_data[self.user_id]["보유금액"] += self.amount

            # 충전 완료 메시지
            await interaction.response.send_message(f"{self.amount:,}원이 성공적으로 충전되었습니다.", ephemeral=True)

            # DM으로 사용자에게 충전 완료 메시지 전송
            user = bot.get_user(self.user_id)
            if user:
                dm_channel = await user.create_dm()

                # 박스 형태로 메시지 꾸미기
                embed = discord.Embed(
                    title="💰 충전 완료",
                    description=f"**{self.amount:,}원**이 성공적으로 충전되었습니다.\n보유 금액이 업데이트되었습니다!",
                    color=discord.Color.green()
                )
                embed.set_footer(text="충전 내역을 확인하세요.")
                
                await dm_channel.send(embed=embed)

            # 채널 닫기
            overwrites = {
                self.channel.guild.default_role: discord.PermissionOverwrite(read_messages=False)
            }
            await self.channel.edit(overwrites=overwrites, name=f"closed-{self.channel.name}")

            # 로그 채널에 메시지 전송
            log_channel = bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="🔔 충전 완료",
                    description=f"{self.amount:,}원이 충전되었습니다. 채널: {self.channel.name}",
                    color=discord.Color.green()
                )
                await log_channel.send(embed=log_embed)

            # 1분 후 채널 삭제
            await asyncio.sleep(60)
            await self.channel.delete()

            if log_channel:
                log_embed = discord.Embed(
                    title="❌ 채널 삭제",
                    description=f"채널: {self.channel.name}",
                    color=discord.Color.red()
                )
                await log_channel.send(embed=log_embed)
        else:
            await interaction.response.send_message("충전 완료는 관리자만 가능합니다.", ephemeral=True)

    async def send_log_and_response(depositor_name, amount, new_channel, interaction, user):
        # 로그 채널에 메시지 전송
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(
                title="🔔 충전 채널 생성",
                description=f"입금자명: {depositor_name}\n금액: {amount}원\n채널: {new_channel.mention}",
                color=discord.Color.green()
            )
            await log_channel.send(embed=log_embed)

        # 사용자에게 응답
        await interaction.response.send_message(f"{user.mention}, 새로운 충전 채널이 열렸습니다: {new_channel.mention}", ephemeral=True)

        # 로그 채널에 메시지 전송
        del active_channels["charge"][interaction.user.id]

        if log_channel:
            log_embed = discord.Embed(
                title="🚪 채널 삭제 예정",
                description=f"채널: {new_channel.name} (삭제 예정)",
                color=discord.Color.red()
            )
            await log_channel.send(embed=log_embed)

        # 1분 후에 채널 삭제
        await asyncio.sleep(60)
        await new_channel.delete()

        if log_channel:
            log_embed = discord.Embed(
                title="❌ 완전 삭제",
                description=f"채널: {new_channel.name}",
                color=discord.Color.red()
            )
            await log_channel.send(embed=log_embed)

# 문의 버튼 View 클래스
class InquiryButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="문의하기", style=discord.ButtonStyle.primary)
    async def inquiry_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_support_channel(interaction)

# 기존 메시지 삭제 함수
async def delete_existing_messages(channel):
    async for message in channel.history(limit=None):
        await message.delete()

# 봇이 준비되었을 때 실행되는 이벤트
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    bot.loop.create_task(log_data_periodically())

    guild = bot.guilds[0]  # 봇이 연결된 첫 번째 서버를 선택
    for member in guild.members:
        # 유저 정보를 기본값으로 저장
        if member.id not in user_data:
            user_data[member.id] = {
                "구매금액": 0,
                "보유금액": 0,
            }

    # 인증 메시지를 보낼 채널 가져오기
    verification_channel = bot.get_channel(verification_channel_id)
    if verification_channel:
        # 기존 메시지 삭제
        await delete_existing_messages(verification_channel)

        # 인증 메시지를 Embed로 꾸미기
        embed = discord.Embed(
            title="🛡️ 서버 인증 안내",
            description=(
                "서버에 접근하려면 아래 **✔인증하기** 버튼을 눌러주세요.\n\n"
                "인증 후, 추가적인 채널과 기능을 이용할 수 있습니다!"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/1068698099108823060/1098916578852085821/31a72afda250825d993400c3ef28c55c.gif?ex=66de2391&is=66dcd211&hm=4ad29b3cbe05157febe0afb2efb0af43da7359e350d920142038277905825366&")
        embed.set_footer(text="인증을 통해 더 많은 기능을 이용하세요!")

        # 인증 버튼이 포함된 메시지 전송
        view = VerificationView()
        await verification_channel.send(embed=embed, view=view)

    # test 채널에서 기존 메시지 삭제 후 새로운 메시지 보내기
    test_channel = bot.get_channel(test_channel_id)

    if test_channel:
        await delete_existing_messages(test_channel)
        view = TestView()

        # test 채널 메시지 보기 좋게 꾸미기
        embed = discord.Embed(
            title="원하시는 기능을 선택해주세요.",
            color=discord.Color.blue()
        )
        await test_channel.send(embed=embed, view=view)

    admin_channel = bot.get_channel(admin_channel_id)

    if admin_channel:
        await delete_existing_messages(admin_channel)
        view = AdminView()
        await admin_channel.send("✔서버 관리기능✔", view=view)

    # 문의하기 버튼을 추가할 채널에 대한 처리 (이전 코드 유지)
    inquiry_channel = bot.get_channel(1282264123849314395)  # 문의 관련 채널 ID를 사용
    if inquiry_channel:
        await delete_existing_messages(inquiry_channel)
        inquiry_view = InquiryButtonView()
        embed = discord.Embed(
            title="📩 문의하기",
            description=(
            "문의사항이 있으시면 아래 **문의하기** 버튼을 눌러주세요.\n\n"
            "```yaml\n"
            "관리자가 확인 후 답변드리겠습니다.\n"
            "```"
            ),
            color=discord.Color.blue()
        )
        await inquiry_channel.send(embed=embed, view=inquiry_view)

# 사용자가 서버에 입장했을 때 실행되는 이벤트
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(welcome_channel_id)  # 환영 메시지를 보낼 채널

    if channel:
        # 환영 메시지 형식
        welcome_message = (
            f"👋 어서오세요, {member.mention}님!\n\n"
            "```diff\n"
            "+ 규칙\n"
            "- 이 서버에서는 비난이나 조롱하는 행위를 금지하고 있습니다.\n"
            "- 모든 제품 구매는 설명 채널에서 확인한 후 진행해주세요.\n"
            "- 규칙을 반드시 준수해 주시기 바랍니다.\n"
            "```"
        )

        # 임의의 GIF 링크 추가 (원하는 GIF URL로 변경 가능)
        gif_url = "https://cdn.discordapp.com/attachments/1077638556832505977/1078726107337080962/-.gif?ex=66dddaf9&is=66dc8979&hm=1b092dbbd7cdcb991f008c274d50241ac92f337ee91625f2a9d3ba757be90a55&"

        # 박스 형식의 메시지와 GIF를 포함한 환영 메시지 생성
        embed = discord.Embed(description=welcome_message, color=discord.Color.blue())
        embed.set_image(url=gif_url)

        # 환영 메시지 전송
        await channel.send(embed=embed)

# 카테고리 선택 View
class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=category, description=f"{category}에서 제품을 선택하세요.")
            for category in product_data.keys()
        ]
        super().__init__(placeholder="카테고리를 선택하세요", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]
        view = ProductSelectView(selected_category)
        await interaction.response.send_message(f"'{selected_category}' 카테고리에서 제품을 선택하세요.", view=view, ephemeral=True)

class ProductSelect(discord.ui.Select):
    def __init__(self, category):
        self.category = category
        options = [
            discord.SelectOption(label=product_name, description=f"가격: {info['price']}원, 재고: {info['stock']}개")
            for product_name, info in product_data[category].items()
        ]
        super().__init__(placeholder="구매할 제품을 선택하세요", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_product = self.values[0]

        # 수량을 입력하는 양식 창 클래스
        class PurchaseQuantityForm(discord.ui.Modal):
            def __init__(self, category, product):
                super().__init__(title=f"{product} 구매 수량 입력")
                self.category = category
                self.product = product
                self.quantity_input = discord.ui.TextInput(label="구매 수량", placeholder="숫자를 입력하세요", required=True)

                # 모달에 입력 필드 추가
                self.add_item(self.quantity_input)

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    quantity = int(self.quantity_input.value)
                except ValueError:
                    await interaction.response.send_message("유효한 숫자를 입력하세요.", ephemeral=True)
                    return

                product_info = product_data[self.category][self.product]

                # 재고 및 보유 금액 체크
                total_price = product_info["price"] * quantity
                if user_data[interaction.user.id]["보유금액"] < total_price:
                    await interaction.response.send_message("보유 금액이 부족합니다.", ephemeral=True)
                elif product_info["stock"] < quantity:
                    await interaction.response.send_message("재고가 부족합니다.", ephemeral=True)
                else:
                    # 구매 완료 후 새로운 채널 생성
                    await create_purchase_channel(interaction.user, self.category, self.product, quantity)
                    await interaction.response.send_message(f"{self.product}을(를) {quantity}개 성공적으로 구매 요청하였습니다! 관리자 확인 후 보유 금액이 차감됩니다.", ephemeral=True)

        # 수량 입력 모달 띄우기
        modal = PurchaseQuantityForm(self.category, selected_product)
        await interaction.response.send_modal(modal)

async def create_purchase_channel(user, category, product_name, quantity):
    guild = user.guild
    category_channel = discord.utils.get(guild.categories, name="Purchase")

    if not category_channel:
        category_channel = await guild.create_category(name="Purchase")

    # 유저와 관리자에게만 보이는 채널 생성
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True),
        guild.get_member(admin_user_id): discord.PermissionOverwrite(read_messages=True)
    }

    channel_name = f"{user.display_name}-{product_name}-{quantity}"
    new_channel = await category_channel.create_text_channel(name=channel_name, overwrites=overwrites)

    # 박스 형태로 메시지 꾸미기
    embed = discord.Embed(
        title="🛒 구매 요청 접수",
        description=(
            f"**구매자:** {user.display_name}\n"
            f"**카테고리:** {category}\n"
            f"**제품명:** {product_name}\n"
            f"**수량:** {quantity}개\n\n"
            "```yaml\n"
            "구매 요청이 접수되었습니다. 관리자 확인 후 보유 금액이 차감됩니다.\n"
            "```"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="문의 채널을 닫으려면 '문의종료' 버튼을 눌러주세요. 구매 완료는 관리자만 가능합니다.")

    # 관리자 호출 멘션
    view = PurchaseCloseView(new_channel, user.id, category, product_name, quantity)
    await new_channel.send(content=f"<@&1281612006205554770>", embed=embed, view=view)

    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        log_embed = discord.Embed(
            title="🔔 구매 채널 생성",
            description=f"유저:{user.mention}.: {new_channel.mention}",
            color=discord.Color.green()
        )
        await log_channel.send(embed=log_embed)
class PurchaseCloseView(discord.ui.View):
    def __init__(self, channel, user_id, category, product_name, quantity):
        super().__init__(timeout=None)
        self.channel = channel
        self.user_id = user_id
        self.category = category
        self.product_name = product_name
        self.quantity = quantity
        self.total_price = product_data[category][product_name]["price"] * quantity

        # 구매 요청 시, 보유 금액과 재고를 임시로 차감
        user_data[self.user_id]["보유금액"] -= self.total_price
        product_data[category][product_name]["stock"] -= quantity

    @discord.ui.button(label="문의닫기", style=discord.ButtonStyle.danger)
    async def close_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 문의취소 시 차감된 보유금액과 재고를 복구
        user_data[self.user_id]["보유금액"] += self.total_price
        product_data[self.category][self.product_name]["stock"] += self.quantity

        view = InquiryCloseConfirmView(self.channel)
        await interaction.response.send_message("정말로 이 채널을 닫으시겠습니까?", view=view, ephemeral=True)

    @discord.ui.button(label="구매완료", style=discord.ButtonStyle.success)
    async def complete_purchase_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == admin_user_id:
            # 구매 완료 시 보유금액은 이미 차감되었으므로 총 구매금액만 증가
            user_data[self.user_id]["구매금액"] += self.total_price
            await interaction.response.send_message("구매가 완료되었습니다. 채널을 닫아주세요.", ephemeral=True)

            # DM으로 평점 및 후기 요청
            await self.send_review_request(self.user_id)

            # 권한 제거 및 채널 이름 변경
            overwrites = {
                self.channel.guild.default_role: discord.PermissionOverwrite(read_messages=False)
            }
            await self.channel.edit(overwrites=overwrites, name=f"closed-{self.channel.name}")

            # 로그 채널에 메시지 전송
            log_channel = bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="🚪 채널 삭제 예정",
                    description=f"채널: {self.channel.name} (삭제 예정)",
                    color=discord.Color.red()
                )
                await log_channel.send(embed=log_embed)

            # 1분 후에 채널 삭제
            await asyncio.sleep(60)
            await self.channel.delete()

            if log_channel:
                log_embed = discord.Embed(
                    title="❌ 완전 삭제",
                    description=f"채널: {self.channel.name}",
                    color=discord.Color.red()
                )
                await log_channel.send(embed=log_embed)
        else:
            await interaction.response.send_message("구매 완료는 관리자만 가능합니다.", ephemeral=True)

    async def send_review_request(self, user_id):
        user = bot.get_user(user_id)
        if not user:
            return

        class ReviewSelect(discord.ui.Select):
            def __init__(self, user_id):
                self.user_id = user_id
                options = [
                    discord.SelectOption(label="⭐", value="1"),
                    discord.SelectOption(label="⭐⭐", value="2"),
                    discord.SelectOption(label="⭐⭐⭐", value="3"),
                    discord.SelectOption(label="⭐⭐⭐⭐", value="4"),
                    discord.SelectOption(label="⭐⭐⭐⭐⭐", value="5")
                ]
                super().__init__(placeholder="평점을 선택하세요", options=options)

            async def callback(self, interaction: discord.Interaction):
                selected_rating = self.values[0]

                class ReviewModal(discord.ui.Modal):
                    def __init__(self, rating, user_id):
                        super().__init__(title="후기 작성")
                        self.rating = rating
                        self.user_id = user_id
                        self.review_input = discord.ui.TextInput(label="후기", placeholder="후기를 작성하세요", required=True)
                        self.add_item(self.review_input)

                    async def on_submit(self, interaction: discord.Interaction):
                        review_channel = bot.get_channel(1284160366485573714)
                        user = bot.get_user(self.user_id)
                        embed = discord.Embed(
                            title="📝 구매 후기",
                            description=(
                                f"**구매자:** {user.display_name}\n"
                                f"**평점:** {'⭐' * int(self.rating)}\n"
                                f"**후기:** {self.review_input.value}\n"
                            ),
                            color=discord.Color.blue()
                        )
                        await review_channel.send(embed=embed)
                        await interaction.response.send_message("후기가 성공적으로 제출되었습니다.", ephemeral=True)

                modal = ReviewModal(selected_rating, self.user_id)
                await interaction.response.send_modal(modal)

        view = discord.ui.View()
        view.add_item(ReviewSelect(user_id))
        await user.send("구매가 완료되었습니다! 평점을 선택하고 후기를 남겨주세요.", view=view)

# 제품 선택 View를 제공하는 클래스
class ProductSelectView(discord.ui.View):
    def __init__(self, category):
        super().__init__(timeout=None)
        self.add_item(ProductSelect(category))

# TestView 클래스
class TestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="내정보", style=discord.ButtonStyle.primary)
    async def info_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        user_info = user_data.get(user_id)

        if user_info:
            purchase_amount = user_info["구매금액"]
            balance = user_info["보유금액"]

            # 정보 표시 (깔끔한 박스 형식)
            info_message = (
                f"**{interaction.user.display_name}님의 정보**\n"
                f"> 등급: **{get_user_grade(purchase_amount)}**\n"
                f"> 총 구매 금액: **{purchase_amount:,}원**\n"
                f"> 보유 금액: **{balance:,}원**"
            )

            embed = discord.Embed(description=info_message, color=discord.Color.blue())

            # 아바타가 있으면 그 아바타를, 없으면 기본 아바타로 설정
            avatar_url = interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
            embed.set_thumbnail(url=avatar_url)

            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("유저 정보를 찾을 수 없습니다.", ephemeral=True)

    @discord.ui.button(label="충전", style=discord.ButtonStyle.success)
    async def charge_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        class ChargeForm(discord.ui.Modal):
            def __init__(self):
                super().__init__(title="충전 양식")

            name_input = discord.ui.TextInput(label="입금자명", required=True)
            amount_input = discord.ui.TextInput(label="충전 금액", required=True, style=discord.TextStyle.short, placeholder="숫자만 입력하세요", min_length=4, max_length=10)

            async def on_submit(self, interaction: discord.Interaction):
                depositor_name = self.name_input.value
                amount = int(self.amount_input.value)

                # 최소 충전 금액 검증
                if amount < 1000:
                    await interaction.response.send_message("충전 금액은 최소 1000원 이상이어야 합니다.", ephemeral=True)
                    return

                # 충전 처리 및 새로운 채널 생성
                await create_charge_channel(depositor_name, amount, interaction)

        modal = ChargeForm()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="제품", style=discord.ButtonStyle.secondary)
    async def product_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 제품 및 재고 정보 출력 (카테고리별로 구분)
        embed = discord.Embed(title="제품 목록", color=discord.Color.gold())

        for category, products in product_data.items():
            product_list = "\n".join([f"**{name}** - 가격: {info['price']}원 | 재고: {info['stock']}개" for name, info in products.items()])
            embed.add_field(name=f"📦 {category}", value=product_list, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="구매", style=discord.ButtonStyle.primary)
    async def purchase_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CategorySelectView()  # 카테고리 선택 View를 표시
        await interaction.response.send_message("카테고리를 선택해주세요", view=view, ephemeral=True)

# 카테고리 선택 View를 제공하는 클래스
class CategorySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CategorySelect())

# AdminView 클래스 (관리자 전용 기능)
class AdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="관리자 기능을 선택하세요",
        options=[
            discord.SelectOption(label="✔보유금액 설정", description="유저의 보유 금액을 설정합니다.", value="fill"),
            discord.SelectOption(label="💥폭파", description="채널의 모든 메시지를 삭제합니다.", value="explode"),
            discord.SelectOption(label="🛡상품관리", description="상품을 설정, 추가, 삭제합니다.", value="manage_product"),
            discord.SelectOption(label="🛡카테고리관리", description="카테고리를 설정, 추가, 삭제합니다.", value="manage_category"),
            discord.SelectOption(label="🔼데이터 출력", description="유저 및 상품 데이터를 출력합니다.", value="data_output"),
            discord.SelectOption(label="🔽데이터 삽입", description="암호화된 데이터를 입력합니다.", value="data_insert"),
            discord.SelectOption(label="💀봇 종료", description="봇을 종료합니다.", value="shutdown")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "fill":
            await self.fill_button_callback(interaction)
        elif select.values[0] == "explode":
            await self.explode_button_callback(interaction)
        elif select.values[0] == "manage_product":
            await self.manage_product_callback(interaction)
        elif select.values[0] == "manage_category":
            await self.manage_category_callback(interaction)
        elif select.values[0] == "data_output":
            await self.data_output_button_callback(interaction)
        elif select.values[0] == "data_insert":
            await self.data_insert_button_callback(interaction)
        elif select.values[0] == "shutdown":
            await self.shutdown_button_callback(interaction)

    # 보유 금액 설정 기능
    async def fill_button_callback(self, interaction: discord.Interaction):
        class FillForm(discord.ui.Modal):
            def __init__(self):
                super().__init__(title="채우기 양식")

            user_id_input = discord.ui.TextInput(label="유저 ID", required=True)
            amount_input = discord.ui.TextInput(label="충전 금액", required=True, placeholder="숫자만 입력하세요")

            async def on_submit(self, interaction: discord.Interaction):
                user_id = int(self.user_id_input.value)
                amount = int(self.amount_input.value)
                if user_id in user_data:
                    user_data[user_id]["보유금액"] += amount
                    await interaction.response.send_message(f"유저 ID {user_id}의 보유 금액이 {amount}원 추가되었습니다.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"유저 ID {user_id}를 찾을 수 없습니다.", ephemeral=True)

        await interaction.response.send_modal(FillForm())

    # 폭파 기능
    async def explode_button_callback(self, interaction: discord.Interaction):
        class ExplodeChannelSelect(discord.ui.Select):
            def __init__(self, guild: discord.Guild):
                options = [discord.SelectOption(label=channel.name, description=f"ID: {channel.id}", value=str(channel.id))
                           for channel in guild.text_channels]
                super().__init__(placeholder="폭파할 채널을 선택하세요", options=options)

            async def callback(self, interaction: discord.Interaction):
                selected_channel_id = int(self.values[0])
                channel = interaction.guild.get_channel(selected_channel_id)
                if channel:
                    await channel.purge()
                    await interaction.response.send_message(f"채널의 모든 메시지가 삭제되었습니다.", ephemeral=True)

        view = discord.ui.View()
        view.add_item(ExplodeChannelSelect(interaction.guild))
        await interaction.response.send_message("폭파할 채널을 선택하세요.", view=view, ephemeral=True)

    # 상품 관리 기능
    async def manage_product_callback(self, interaction: discord.Interaction):
        class ManageProductView(discord.ui.View):
            @discord.ui.button(label="설정", style=discord.ButtonStyle.primary)
            async def setting_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                class ProductSelect(discord.ui.Select):
                    def __init__(self):
                        options = []
                        for category, products in product_data.items():
                            for product_name in products:
                                options.append(discord.SelectOption(label=product_name, description=f"{category}에 속하는 제품입니다."))

                        super().__init__(placeholder="설정할 상품을 선택하세요", options=options)

                    async def callback(self, interaction: discord.Interaction):
                        selected_product = self.values[0]
                        for category, products in product_data.items():
                            if selected_product in products:
                                await interaction.response.send_modal(ProductSettingForm(category, selected_product))
                                break

                product_select_view = discord.ui.View()
                product_select_view.add_item(ProductSelect())
                await interaction.response.send_message("설정할 상품을 선택하세요.", view=product_select_view, ephemeral=True)

            @discord.ui.button(label="추가", style=discord.ButtonStyle.success)
            async def add_product_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                class CategorySelect(discord.ui.Select):
                    def __init__(self):
                        options = [
                            discord.SelectOption(label=category, description=f"{category}에 상품을 추가합니다.")
                            for category in product_data.keys()
                        ]
                        super().__init__(placeholder="카테고리를 선택하세요", options=options)

                    async def callback(self, interaction: discord.Interaction):
                        selected_category = self.values[0]

                        class ProductAddForm(discord.ui.Modal):
                            def __init__(self, category):
                                super().__init__(title=f"{category}에 상품 추가")
                                self.category = category
                                self.product_name_input = discord.ui.TextInput(label="상품 이름", required=True)
                                self.price_input = discord.ui.TextInput(label="가격", required=True)
                                self.stock_input = discord.ui.TextInput(label="재고 수", required=True)
                                self.add_item(self.product_name_input)
                                self.add_item(self.price_input)
                                self.add_item(self.stock_input)

                            async def on_submit(self, interaction: discord.Interaction):
                                product_name = self.product_name_input.value
                                price = int(self.price_input.value)
                                stock = int(self.stock_input.value)

                                product_data[self.category][product_name] = {"price": price, "stock": stock}
                                await interaction.response.send_message(f"{self.category}에 {product_name}가 추가되었습니다.", ephemeral=True)

                        await interaction.response.send_modal(ProductAddForm(selected_category))

                category_view = discord.ui.View()
                category_view.add_item(CategorySelect())
                await interaction.response.send_message("상품을 추가할 카테고리를 선택하세요.", view=category_view, ephemeral=True)

            @discord.ui.button(label="삭제", style=discord.ButtonStyle.danger)
            async def delete_product_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                class ProductDeleteSelect(discord.ui.Select):
                    def __init__(self):
                        options = []
                        for category, products in product_data.items():
                            for product_name in products:
                                options.append(discord.SelectOption(label=product_name, description=f"{category}에 속하는 제품입니다."))

                        super().__init__(placeholder="삭제할 상품을 선택하세요", options=options)

                    async def callback(self, interaction: discord.Interaction):
                        selected_product = self.values[0]
                        for category, products in product_data.items():
                            if selected_product in products:
                                del product_data[category][selected_product]
                                await interaction.response.send_message(f"{selected_product}이(가) 삭제되었습니다.", ephemeral=True)
                                break

                product_delete_view = discord.ui.View()
                product_delete_view.add_item(ProductDeleteSelect())
                await interaction.response.send_message("삭제할 상품을 선택하세요.", view=product_delete_view, ephemeral=True)

        view = ManageProductView()
        await interaction.response.send_message("상품 관리 기능을 선택하세요: 설정, 추가, 삭제", view=view, ephemeral=True)

    # 카테고리 관리 기능
    async def manage_category_callback(self, interaction: discord.Interaction):
        class ManageCategoryView(discord.ui.View):
            @discord.ui.button(label="설정", style=discord.ButtonStyle.primary)
            async def setting_category_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                class CategorySelect(discord.ui.Select):
                    def __init__(self):
                        options = [
                            discord.SelectOption(label=category, description=f"{category}의 이름을 변경합니다.")
                            for category in product_data.keys()
                        ]
                        super().__init__(placeholder="설정할 카테고리를 선택하세요", options=options)

                    async def callback(self, interaction: discord.Interaction):
                        selected_category = self.values[0]

                        class CategorySettingForm(discord.ui.Modal):
                            def __init__(self, category):
                                super().__init__(title=f"{category} 설정")
                                self.category = category
                                self.new_name_input = discord.ui.TextInput(label="새 카테고리 이름", required=True)
                                self.add_item(self.new_name_input)

                            async def on_submit(self, interaction: discord.Interaction):
                                new_name = self.new_name_input.value
                                if new_name in product_data:
                                    await interaction.response.send_message(f"{new_name} 카테고리는 이미 존재합니다.", ephemeral=True)
                                else:
                                    product_data[new_name] = product_data.pop(self.category)
                                    await interaction.response.send_message(f"{self.category}의 이름이 {new_name}(으)로 변경되었습니다.", ephemeral=True)

                        await interaction.response.send_modal(CategorySettingForm(selected_category))

                category_select_view = discord.ui.View()
                category_select_view.add_item(CategorySelect())
                await interaction.response.send_message("설정할 카테고리를 선택하세요.", view=category_select_view, ephemeral=True)

            @discord.ui.button(label="추가", style=discord.ButtonStyle.success)
            async def add_category_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                class CategoryAddForm(discord.ui.Modal):
                    def __init__(self):
                        super().__init__(title="카테고리 추가")
                        self.category_name_input = discord.ui.TextInput(label="카테고리 이름", required=True)
                        self.add_item(self.category_name_input)

                    async def on_submit(self, interaction: discord.Interaction):
                        category_name = self.category_name_input.value

                        if category_name not in product_data:
                            product_data[category_name] = {}
                            await interaction.response.send_message(f"{category_name} 카테고리가 추가되었습니다.", ephemeral=True)
                        else:
                            await interaction.response.send_message(f"{category_name} 카테고리가 이미 존재합니다.", ephemeral=True)

                await interaction.response.send_modal(CategoryAddForm())

            @discord.ui.button(label="삭제", style=discord.ButtonStyle.danger)
            async def delete_category_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                class CategoryDeleteSelect(discord.ui.Select):
                    def __init__(self):
                        options = [
                            discord.SelectOption(label=category, description=f"{category} 내의 모든 상품을 삭제합니다.")
                            for category in product_data.keys()
                        ]
                        super().__init__(placeholder="삭제할 카테고리를 선택하세요", options=options)

                    async def callback(self, interaction: discord.Interaction):
                        selected_category = self.values[0]
                        if selected_category in product_data:
                            del product_data[selected_category]
                            await interaction.response.send_message(f"{selected_category} 카테고리 및 그 안의 모든 상품이 삭제되었습니다.", ephemeral=True)

                category_delete_view = discord.ui.View()
                category_delete_view.add_item(CategoryDeleteSelect())
                await interaction.response.send_message("삭제할 카테고리를 선택하세요.", view=category_delete_view, ephemeral=True)

        view = ManageCategoryView()
        await interaction.response.send_message("카테고리 관리 기능을 선택하세요: 설정, 추가, 삭제", view=view, ephemeral=True)

    # 데이터 출력 기능
    async def data_output_button_callback(self, interaction: discord.Interaction):
        combined_data = {"user_data": user_data, "product_data": product_data}
        output_message = json.dumps(combined_data, ensure_ascii=False)
        encrypted_output = encrypt_data(output_message)
        await interaction.response.send_message(f"암호화된 데이터:\n```{encrypted_output}```", ephemeral=True)

    # 데이터 삽입 기능
    async def data_insert_button_callback(self, interaction: discord.Interaction):
        class DataInsertForm(discord.ui.Modal):
            def __init__(self):
                super().__init__(title="데이터 삽입 양식")
                self.encrypted_data_input = discord.ui.TextInput(label="암호화된 데이터", style=discord.TextStyle.long, required=True)
                self.add_item(self.encrypted_data_input)

            async def on_submit(self, interaction: discord.Interaction):
                encrypted_data = self.encrypted_data_input.value
                try:
                    decrypted_data = decrypt_data(encrypted_data)
                    data = json.loads(decrypted_data)

                    for user_id_str, user_info in data.get("user_data", {}).items():
                        user_id = int(user_id_str)
                        user_data[user_id] = user_info

                    product_data.update(data.get("product_data", {}))

                    await interaction.response.send_message("데이터가 성공적으로 입력되었습니다.", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"오류 발생: {str(e)}", ephemeral=True)

        await interaction.response.send_modal(DataInsertForm())

    # 봇 종료 기능 (각 채널에 오프라인 메시지를 Embed로 예쁘게 꾸미기)
    async def shutdown_button_callback(self, interaction: discord.Interaction):
        if interaction.user.id == admin_user_id:
            # 종료 시 각 채널에 전송할 메시지
            offline_message = "현재 봇을 이용할 수 없습니다."
            gif_url = "https://cdn.discordapp.com/attachments/1282258321222402070/1286915533991706685/ezgif-3-533a70a740.gif?ex=66efa4fd&is=66ee537d&hm=0a210b03ee2a1fdcc5a9697e57eb245723b8ca6f9b08643918695d7e9767a437&"  # 원하는 GIF URL로 변경

            # Embed 형태로 메시지 꾸미기
            embed = discord.Embed(
                title="🔴 봇 오프라인 알림",
                description=offline_message,
                color=discord.Color.red()
            )
            embed.set_image(url=gif_url)
            embed.set_footer(text="봇이 안전하게 종료되었습니다.")

            # 채널 ID들
            test_channel = bot.get_channel(test_channel_id)
            verification_channel = bot.get_channel(verification_channel_id)
            inquiry_channel = bot.get_channel(1282264123849314395)  # 문의 관련 채널 ID
            admin_channel = bot.get_channel(admin_channel_id)

            # 각 채널에 Embed 메시지 전송
            if test_channel:
                await delete_existing_messages(test_channel)
                await test_channel.send(embed=embed)
            if verification_channel:
                await delete_existing_messages(verification_channel)
                await verification_channel.send(embed=embed)
            if inquiry_channel:
                await delete_existing_messages(inquiry_channel)
                await inquiry_channel.send(embed=embed)
            if admin_channel:
                await delete_existing_messages(admin_channel)

            # 종료 데이터 로그를 남기고 봇 종료
            combined_data = {"user_data": user_data, "product_data": product_data}
            output_message = json.dumps(combined_data, ensure_ascii=False)
            encrypted_output = encrypt_data(output_message)

            log_channel = bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="🔒 암호화된 종료 데이터",
                    description=f"```{encrypted_output}```",
                    color=discord.Color.red()
                )
                log_embed.set_footer(text="봇이 종료됩니다.")
                await log_channel.send(embed=log_embed)
            # 관리자에게 종료 메시지
            try:
                await interaction.response.send_message("봇이 종료됩니다.", ephemeral=True)
            except discord.errors.NotFound:
                print("error")
                pass
            await bot.close()
        else:
            await interaction.response.send_message("권한이 없습니다.", ephemeral=True)


# ProductSettingForm 클래스 (상품 수정 기능) - 이름도 수정 가능
class ProductSettingForm(discord.ui.Modal):
    def __init__(self, category, product_name):
        super().__init__(title=f"{product_name} 수정")
        self.category = category
        self.original_product_name = product_name

        product_info = product_data[category][product_name]

        # 상품 이름 수정 필드 추가
        self.name_input = discord.ui.TextInput(label="상품 이름", default=product_name, required=True)
        self.price_input = discord.ui.TextInput(label="가격", default=str(product_info["price"]), required=True)
        self.stock_input = discord.ui.TextInput(label="재고 수", default=str(product_info["stock"]), required=True)

        # 모달에 입력 필드 추가
        self.add_item(self.name_input)
        self.add_item(self.price_input)
        self.add_item(self.stock_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value
        price = int(self.price_input.value)
        stock = int(self.stock_input.value)

        # 상품 이름이 변경될 경우 처리
        if new_name != self.original_product_name:
            if new_name in product_data[self.category]:
                await interaction.response.send_message(f"상품 이름 '{new_name}'은(는) 이미 존재합니다.", ephemeral=True)
                return
            else:
                # 기존 상품 삭제 및 새 이름으로 추가
                product_data[self.category][new_name] = product_data[self.category].pop(self.original_product_name)

        # 가격 및 재고 업데이트
        product_data[self.category][new_name]["price"] = price
        product_data[self.category][new_name]["stock"] = stock

        await interaction.response.send_message(f"'{new_name}' 상품의 정보가 업데이트되었습니다.", ephemeral=True)


# VerificationView 클래스 (인증 기능)
class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✔인증하기", style=discord.ButtonStyle.success)
    async def verify_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(verification_role_id)
        if role:
            if role not in interaction.user.roles:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"{interaction.user.mention}님에게 인증 역할이 부여되었습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("이미 인증 역할을 가지고 있습니다.", ephemeral=True)

# 봇 실행 (YOUR_BOT_TOKEN을 실제 디스코드 봇 토큰으로 교체)
bot.run("MTI4NjY1OTAzNzY3NjU3MjcxMw.G3vrch.Xu2kN_5wbYUiyCb0iIoSz39zUvCV0P4KqmbDcg")
