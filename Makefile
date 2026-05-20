HOST ?= overleaf

.PHONY: deploy deploy-reminder ping check check-reminder setup-secrets

setup-secrets:
	@test -f secrets.yml || cp secrets.yml.example secrets.yml

deploy: setup-secrets
	ansible-playbook playbooks/deploy.yml --limit $(HOST)

deploy-reminder: setup-secrets
	ansible-playbook playbooks/reminder.yml --limit $(HOST)

ping:
	ansible $(HOST) -m ping

check:
	ansible-playbook playbooks/deploy.yml --limit $(HOST) --check --diff

check-reminder:
	ansible-playbook playbooks/reminder.yml --limit $(HOST) --check --diff
