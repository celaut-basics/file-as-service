"""Stage shared code and choose pack architecture (no implicit host detection)."""
import argparse,json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--arch',choices=['arm64','amd64'],default='arm64');a=p.parse_args()
for kind in ('film','game','pdf'):
    service=root/kind/'service';shutil.copyfile(root/'common/http_base.py',service/'http_base.py')
    (service/'entrypoint.sh').write_text('#!/bin/sh\nexport PATH=/usr/local/bin:/usr/bin:/bin\ncd /service\nexec python3 /service/app.py\n')
    (service/'entrypoint.sh').chmod(0o755)
    config={'tag':'file-as-service-'+kind,'architecture':'linux/'+a.arch,'init':{'entry_path':['service','entrypoint.sh']},'api':[{'port':8080,'transport':'tcp','protocol':['http','file-as-service-'+kind]}],'network':[],'resources':{'at_init':{'mem_limit':268435456,'disk_space':1073741824,'cpu_period':100000,'cpu_quota':200000},'at_most':{'mem_limit':536870912,'disk_space':2147483648,'cpu_period':100000,'cpu_quota':400000}}}
    (root/kind/'.service/service.json').write_text(json.dumps(config,indent=2)+'\n')
    (root/kind/'.service/pack_config.json').write_text(json.dumps({'service_dependencies_directory':'__services__','metadata_dependencies_directory':'__metadata__','blocks_directory':'__block__','zip':False,'include':['service']},indent=2)+'\n')
