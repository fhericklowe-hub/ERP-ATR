import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Service, type Site } from './api'

type Compte = {
  id: number; username: string; first_name: string; last_name: string; email: string; telephone: string; fonction: string
  site: number | null; site_nom: string; service: number | null; service_nom: string; roles: string[]; is_active: boolean; mot_de_passe_a_changer: boolean
  administrateur: boolean; derniere_connexion: string | null
}
type Saisie = Pick<Compte, 'username' | 'first_name' | 'last_name' | 'email' | 'telephone' | 'fonction' | 'site' | 'service' | 'roles' | 'is_active' | 'mot_de_passe_a_changer'>
  & { id?: number; mot_de_passe: string; administrateur?: boolean }

const VIDE: Saisie = { username: '', first_name: '', last_name: '', email: '', telephone: '', fonction: '', site: null, service: null, roles: [], is_active: true, mot_de_passe_a_changer: true, mot_de_passe: '' }
const nomDe = (c: Compte) => `${c.first_name} ${c.last_name}`.trim() || c.username

/** Les comptes des utilisateurs et leurs rôles. Un compte ne se supprime pas, il se désactive. */
export default function Comptes({ moi }: { moi: number }) {
  const [liste, setListe] = useState<Compte[] | null>(null)
  const [total, setTotal] = useState(0)
  const [filtre, setFiltre] = useState({ search: '', is_active: 'true' })
  const [fiche, setFiche] = useState<Saisie | null>(null)
  const [roles, setRoles] = useState<string[]>([])
  const [sites, setSites] = useState<Site[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    const q = new URLSearchParams({ search: filtre.search, page_size: '200' })
    if (filtre.is_active) q.set('is_active', filtre.is_active)
    api<Page<Compte>>(`/comptes/?${q}`).then((p) => { setListe(p.results); setTotal(p.count) }).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  useEffect(charger, [charger])
  useEffect(() => {
    api<string[]>('/comptes/roles/').then(setRoles).catch(() => undefined)
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    api<Page<Service>>('/services/?actif=true&page_size=100').then((p) => setServices(p.results)).catch(() => undefined)
  }, [])

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!fiche) return
    setErreur('')
    setEnCours(true)
    try {
      const { id, administrateur: _a, username, mot_de_passe, ...reste } = fiche
      const corps = { ...reste, ...(id ? {} : { username }), ...(mot_de_passe ? { mot_de_passe } : {}) }
      await api(id ? `/comptes/${id}/` : '/comptes/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(corps) })
      setFiche(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  if (fiche) {
    const moiMeme = fiche.id === moi
    const texte = (nom: 'first_name' | 'last_name' | 'email' | 'telephone' | 'fonction') =>
      ({ value: fiche[nom], onChange: (e: { target: { value: string } }) => setFiche({ ...fiche, [nom]: e.target.value }) })
    const modules = [...new Set(roles.map((r) => r.split(' - ')[0]))]
    const basculer = (role: string) => setFiche({ ...fiche, roles: fiche.roles.includes(role) ? fiche.roles.filter((r) => r !== role) : [...fiche.roles, role] })
    return (
      <form className="fiche" onSubmit={enregistrer}>
        <p><a href="#/comptes" onClick={() => setFiche(null)}>← Comptes</a></p>
        <h2>{fiche.id ? `${fiche.first_name} ${fiche.last_name}`.trim() || fiche.username : 'Nouveau compte'}</h2>
        {fiche.administrateur && <p className="aide">Ce compte est celui d'un administrateur : seul un administrateur peut le modifier.</p>}
        <fieldset>
          <legend>Identité</legend>
          <div className="grille">
            <label>Identifiant<input required maxLength={150} pattern="[\w.@+\-]+" title="Lettres, chiffres et . @ + - _" disabled={!!fiche.id} autoFocus={!fiche.id} autoComplete="off"
              value={fiche.username} onChange={(e) => setFiche({ ...fiche, username: e.target.value })} /></label>
            <label>Prénom<input maxLength={150} {...texte('first_name')} /></label>
            <label>Nom<input maxLength={150} {...texte('last_name')} /></label>
            <label>Fonction<input maxLength={100} {...texte('fonction')} /></label>
            <label>E-mail<input type="email" {...texte('email')} /></label>
            <label>Téléphone<input maxLength={30} {...texte('telephone')} /></label>
            <label>Site
              <select value={fiche.site ?? ''} onChange={(e) => setFiche({ ...fiche, site: Number(e.target.value) || null })}><option value="">Non précisé</option>{sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select>
            </label>
            <label>Service
              <select value={fiche.service ?? ''} onChange={(e) => setFiche({ ...fiche, service: Number(e.target.value) || null })}><option value="">Non précisé</option>{services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select>
            </label>
            <label>{fiche.id ? 'Nouveau mot de passe' : 'Mot de passe de départ'}
              <input type="password" autoComplete="new-password" required={!fiche.id} minLength={8} placeholder={fiche.id ? 'Laisser vide pour ne pas le changer' : ''}
                value={fiche.mot_de_passe} onChange={(e) => setFiche({ ...fiche, mot_de_passe: e.target.value, ...(e.target.value && !moiMeme ? { mot_de_passe_a_changer: true } : {}) })} />
            </label>
          </div>
          {!moiMeme && <label className="case"><input type="checkbox" checked={fiche.mot_de_passe_a_changer} onChange={(e) => setFiche({ ...fiche, mot_de_passe_a_changer: e.target.checked })} /> La personne doit choisir son propre mot de passe à sa prochaine connexion</label>}
          <p className="aide">Mot de passe : 8 caractères au moins, pas uniquement des chiffres, pas un mot de passe courant.</p>
          {fiche.id && !moiMeme && <label className="case"><input type="checkbox" checked={fiche.is_active} onChange={(e) => setFiche({ ...fiche, is_active: e.target.checked })} /> Compte actif (décoché : la personne ne peut plus se connecter)</label>}
        </fieldset>
        <fieldset disabled={moiMeme}>
          <legend>Rôles</legend>
          {moiMeme && <p className="aide">On ne change pas ses propres rôles : demandez-le à un autre gestionnaire des comptes.</p>}
          <div className="grille">
          {modules.map((m) => (
            <div key={m} role="group" aria-label={m}>
              <strong>{m}</strong>
              {roles.filter((r) => r.split(' - ')[0] === m).map((r) => (
                <label key={r} className="case"><input type="checkbox" checked={fiche.roles.includes(r)} onChange={() => basculer(r)} /> {r.split(' - ').slice(1).join(' - ') || r}</label>
              ))}
            </div>
          ))}
          </div>
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <div className="actions">
          <button type="button" className="secondaire" onClick={() => { setFiche(null); setErreur('') }}>Annuler</button>
          <button disabled={enCours}>{enCours ? 'Enregistrement…' : 'Enregistrer'}</button>
        </div>
      </form>
    )
  }

  return (
    <>
      <div className="barre">
        <h2>Comptes des utilisateurs</h2>
        <div className="actions"><button onClick={() => { setErreur(''); setFiche(VIDE) }}>Nouveau compte</button></div>
      </div>
      <div className="grille filtres">
        <label>Recherche<input placeholder="Nom, identifiant, fonction" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>Situation
          <select value={filtre.is_active} onChange={(e) => setFiltre({ ...filtre, is_active: e.target.value })}><option value="true">Actifs</option><option value="false">Désactivés</option><option value="">Tous</option></select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucun compte.</p>}
      {liste && liste.length > 0 && (
        <>
          <p className="aide">{total} compte{total > 1 ? 's' : ''}</p>
          <div className="defilant">
            <table>
              <thead><tr><th>Identifiant</th><th>Nom</th><th>Fonction</th><th>Site</th><th>Rôles</th><th>Dernière connexion</th><th></th></tr></thead>
              <tbody>
                {liste.map((c) => (
                  <tr key={c.id}>
                    <td>{c.username}</td>
                    <td>{nomDe(c)}{!c.is_active && <> <span className="pastille">Désactivé</span></>}{c.administrateur && <> <span className="pastille complete">Administrateur</span></>}{c.mot_de_passe_a_changer && <> <span className="pastille">Mot de passe à changer</span></>}</td>
                    <td>{c.fonction}{c.service_nom && <><br /><span className="aide">{c.service_nom}</span></>}</td><td>{c.site_nom}</td>
                    <td>{c.roles.length === 0 ? <span className="aide">Aucun</span> : c.roles.length <= 2 ? c.roles.join(', ') : <span title={c.roles.join('\n')}>{c.roles.length} rôles</span>}</td>
                    <td>{c.derniere_connexion ? new Date(c.derniere_connexion).toLocaleDateString('fr-FR') : <span className="aide">Jamais</span>}</td>
                    <td><button className="secondaire" onClick={() => { setErreur(''); setFiche({ ...c, mot_de_passe: '' }) }}>Modifier</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
