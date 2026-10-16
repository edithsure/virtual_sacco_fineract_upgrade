# Contributing to Virtual SACCO Fineract Upgrade

## Set up your local copy

```powershell
git clone https://github.com/edithsure/virtual_sacco_fineract_upgrade.git
cd .\virtual_sacco_fineract_upgrade
.\setup_project.ps1
```

## Start the app

```powershell
.\start_app.ps1
```

## Default login

- Email: `admin@mwangaza.sacco`
- Password: `Admin123!`

## Recommended workflow

1. Create a feature branch
2. Make focused changes
3. Test locally
4. Commit and push

```powershell
git checkout -b feature/my-update
git add .
git commit -m "Describe the change"
git push origin feature/my-update
```

## Notes

- Do not commit `.env` or real credentials.
- Keep DB files local and untracked.
- Use the `main` branch for stable updates.
