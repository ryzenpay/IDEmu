# In-car plugin half — moved to the `idplugins` project

The in-car half of the plugin system (loader, docs, guest contract) now lives in its own project:
[`../idplugins`](../idplugins). Full contract (package layout, boot order, QNX shell constraints,
live push, recipes): **[idplugins/docs/GUESTPLUGINS.md](../idplugins/docs/GUESTPLUGINS.md)**.

The guest-side hook itself stays here and is generic: `idemu/guest/boot.sh` sources `pre.sh` and
runs `boot.sh` of every package mounted at `/fs/shim/u/` before launching `HmiMain3D`.
