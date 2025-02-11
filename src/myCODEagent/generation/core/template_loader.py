import yaml
def load_config(file):
 with open(file,'r') as f: return yaml.safe_load(f)
def manual_select(domains):
 print("Select a domain:")
 opts=[d for d in domains if d!="generic"]
 for i,d in enumerate(opts): print(f"{i+1}: {d}")
 try: sel=int(input("Enter number: ")); return opts[sel-1] if 1<=sel<=len(opts) else None
 except: return None
def dynamic_select(config):
 scores={d:0 for d in config['domains'] if d!="generic"}
 for q in config['domains']['generic'].get('questions',[]):
  input(q['prompt']+" ")
 for d,data in config['domains'].items():
  if d=="generic": continue
  for q in data.get('questions',[]):
   ans=input(q['prompt']+" ").strip().lower()
   if ans in ["yes","y"]:
    for dom,wt in q.get('weights',{}).items():
     if dom in scores: scores[dom]+=wt
  if scores[d]>=data.get('threshold',0):
   print(f"Domain '{d}' activated (score: {scores[d]})")
   return d,scores
 return "generic",scores
def generate_spec(domain,scores):
 spec=f"Template Spec for domain: {domain}\nScores: {scores}\nSections:\n- General Overview\n"
 if domain!="generic": spec+=f"- {domain.capitalize()} Specific Section\n"
 spec+="Prompts:\n- Include detailed prompts (business, retirement, legal, health, programming, inventions)\nEngineer: use this spec to build the project."
 return spec
def final_confirm(spec):
 print("Generated Spec:\n"+spec)
 return input("Does this spec meet your intent? (yes/no) ").strip().lower() in ["yes","y"]
def update_knowledge_base():
 pass
def main():
 config=load_config("template_config.yml")
 while True:
  if input("Manually select domain? (yes/no) ").strip().lower() in ["yes","y"]:
   domain=manual_select(config['domains'])
   scores={}
  else:
   domain,scores=dynamic_select(config)
  spec=generate_spec(domain,scores)
  if final_confirm(spec): break
  print("Restarting template generation...\n")
 print("Final Template Spec:\n"+spec)
if __name__=="__main__":
 main()
