from pathlib import Path
import hashlib,re
ROOT=Path(__file__).with_name('agent_skills')
GROUPS={'identity-preferences':{'read_thread_user_data','read_user_preferences','read_forme_user_data','thread_user_context','forme_user_context','update_preferences','connection_status','read_forme_orders'},'product-discovery':{'catalog_search','product_details'},'bag-management':{'read_forme_bag','add_to_bag','update_bag_item','remove_bag_item','queued_additions'},'checkout':{'checkout_review','confirm_checkout'},'availability':{'availability_notifications'}}
def for_tool(tool):return next((name for name,names in GROUPS.items() if tool in names),None)
def load(name):
 if name not in GROUPS:raise ValueError('Unknown workflow')
 content=(ROOT/name/'SKILL.md').read_text()
 return {'name':name,'version':re.search(r'version: \"([^\"]+)\"',content)[1],'sha256':hashlib.sha256(content.encode()).hexdigest(),'instructions':content}
def catalog():
 return [{'name':name,'description':load(name)['instructions'].split('description: ',1)[1].splitlines()[0]} for name in GROUPS]
