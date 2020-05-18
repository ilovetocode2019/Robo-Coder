from discord.ext import commands
import discord
import functools
import smtplib, ssl
from datetime import datetime as d
def send_email(sender_email, password, receiver_email, subj, txt, domain):
    port = 587
    smtp_server = "smtp." + domain

    message = """Subject: """ + subj + """\n\n""" + txt + """\nBtw this message is sent from Python."""

    #Send the email
    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, port) as server:
        server.ehlo()  # Can be omitted
        server.starttls(context=context)
        server.ehlo()  # Can be omitted
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message)
        #Show succsesfuly sent message
class Mail(commands.Cog):
    """Sending email"""
    def __init__(self, bot):
        self.bot = bot
    @commands.cooldown(1, 300)
    @commands.command(name="mail", description="Send a email though your DM")
    async def mail(self, ctx):
        def check(ms):
            # Look for the message sent in the same channel where the command was used
            # As well as by the user who used the command.
            return (ms.channel == ctx.channel or ms.channel == ctx.author.dm_channel) and ms.author == ctx.author

        try:
            if not isinstance(ctx.channel, discord.DMChannel):
                await ctx.send("Directing you to a DM")
        except:
            await ctx.send("DMs turned off")
        
        await ctx.author.send("From: ")
        msg = await self.bot.wait_for("message", check = check)
        sender_email = msg.content

        await ctx.author.send("To: ")
        msg = await self.bot.wait_for("message", check = check)
        receiver_email = msg.content

        await ctx.author.send("Subject: ")
        msg = await self.bot.wait_for("message", check = check)
        subject = msg.content

        await ctx.author.send("Message: ")
        msg = await self.bot.wait_for("message", check = check)
        message = msg.content

        await ctx.author.send("Password: ")
        msg = await self.bot.wait_for("message", check = check)
        password = msg.content

        if "@" not in sender_email:
            sender_email = "invalidemailaddress@invaliddomain.com"
        username, domain = sender_email.split("@")
        if domain not in ["outlook.com", "gmail.com", "yahoo.com", "hotmail.com"]:
            await ctx.author.send("SMTP host: ")
            msg = await self.bot.wait_for("message", check = check)
            domain = msg.content

        redoMSG = "Please check the preveiw. Would you like to change the `sender`, `reciever`, `subject`, or `message`?\nType one of those options, or type `send` to send the email."
        while True:
            await ctx.author.send("Preveiw:")
            description = f"To: {receiver_email}\n\n{message}"
            em = discord.Embed(title=subject, description=description,
                           color=0x2F3136, timestamp=d.utcnow())
            em.set_author(name=sender_email, icon_url=ctx.author.avatar_url)
            await ctx.author.send(embed = em)
            await ctx.author.send(redoMSG)
            msg = await self.bot.wait_for("message", check = check)
            choice = msg.content
            if choice == "sender":
                await ctx.author.send("From: ")
                msg = await self.bot.wait_for("message", check = check)
                sender_email = msg.content
            elif choice == "receiver":
                await ctx.author.send("To: ")
                msg = await self.bot.wait_for("message", check = check)
                receiver_email = msg.content
            elif choice == "subject":
                await ctx.author.send("Subject: ")
                msg = await self.bot.wait_for("message", check = check)
                subject = msg.content
            elif choice == "message":
                await ctx.author.send("Message: ")
                msg = await self.bot.wait_for("message", check = check)
                message = msg.content
            elif choice == "send":
                break
            

            
            
 
            
        await ctx.author.send("Atempting to send your email")
        partial = functools.partial(send_email, sender_email, password, receiver_email, subject, message, domain)
        try:
            result = await self.bot.loop.run_in_executor(None, partial)
            await ctx.author.send("Email succsessfully sent!")
        except Exception as e:
            return await ctx.author.send("Error occoured! \n" + str(e))
            



def setup(bot):
    bot.add_cog(Mail(bot))