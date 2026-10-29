"""Small conversational turns never need data access or shopping actions."""
import re

def conversational_reply(text):
 value=text.strip().lower().rstrip('!.? ')
 if re.fullmatch(r'(hello|hi|hey|hiya|good (morning|afternoon|evening))( there| thread)?',value):
  return 'Hello! What would you like help with today? I can find clothes, remember your preferences, or help with your FORME bag.'
 if re.fullmatch(r'(thanks|thank you|thank you so much|thanks a lot|cheers)( thread)?',value):return 'You’re welcome! Let me know what you’d like to do next.'
 if value in ('how are you','how are you doing',"how's it going"):
  return 'I’m ready to help. What are we shopping for today?'
 if value in ('bye','goodbye','see you','see you later'):return 'See you! Your saved preferences will be here when you return.'
 if value in ('help','what can you do','how can you help me'):
  return 'I can find clothes and shoes, remember your Thread preferences, and read your FORME bag or orders after authorization. Tell me what you need. I’ll ask for explicit approval before placing a simulated order.'
 return None

def without_greeting(text):
 return re.sub(r'^(?:hello|hi|hey)(?: thread)?[,!:.]+\s*','',text.strip(),flags=re.I)
