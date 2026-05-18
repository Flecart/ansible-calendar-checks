HOST ?= overleaf

.PHONY: deploy ping check setup-secrets

setup-secrets:
	@test -f secrets.yml || cp secrets.yml.example secrets.yml

deploy: setup-secrets
	ansible-playbook playbooks/deploy.yml --limit $(HOST)

ping:
	ansible $(HOST) -m ping

check:
	ansible-playbook playbooks/deploy.yml --limit $(HOST) --check --diff
