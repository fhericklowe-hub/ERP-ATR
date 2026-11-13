import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { api, type Page } from '../api'

type Qualite = 'fournisseur' | 'client'
type Contact = { id: number; tiers: number; nom: string; fonction: string; telephone: string; email: string }
type Fiche = {
  contacts?: Contact[]
  id: number; code: string; raison_sociale: string; est_client: boolean; est_fournisseur: boolean; numero_contribuable: string
  telephone: string; email: string; adresse: string; ville: string; actif: boolean
}
type Saisie = Omit<Fiche, 'id' | 'contacts'>
type Bilan = { lues: number; crees: number; modifies: number; inchanges: number; erreurs: string[]; simulation: boolean; ecrit: boolean }

const MOTS = {
  fournisseur: { titre: 'Fournisseurs', un: 'fournisseur', nouveau: 'Nouveau fournisseur', base: '/fournisseurs', autre: 'Aussi client' },
  client: { titre: 'Clients', un: 'client', nouveau: 'Nouveau client', base: '/clients', autre: 'Aussi fournisseur' },
}
const vide = (qualite: Qualite): Saisie => ({
  code: '', raison_sociale: '', est_client: qualite === 'client', est_fournisseur: qualite === 'fournisseur', numero_contribuable: '',
  telephone: '', email: '', adresse: '', ville: '', actif: true,
})

/** Fournisseurs ou clients : la même fiche, vue selon la qualité. Une fiche ne se supprime pas, elle se désactive. */
export function ListeTiers({ qualite, peutCreer, peutModifier }: { qualite: Qualite; peutCreer: boolean; peutModifier: boolean }) {
  const mots = MOTS[qualite]
  const [liste, setListe] = useState<Fiche[] | null>(null)
  const [total, setTotal] = useState(0)
  const [filtre, setFiltre] = useState({ search: '', actif: 'true' })
  const [fiche, setFiche] = useState<(Saisie & { id?: number; contacts?: Contact[] }) | null>(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    const q = new URLSearchParams({ [`est_${qualite}`]: 'true', search: filtre.search, page_size: '200' })
    if (filtre.actif) q.set('actif', filtre.actif)
    api<Page<Fiche>>(`/tiers/?${q}`).then((p) => { setListe(p.results); setTotal(p.count) }).catch((e: Error) => setErreur(e.message))
  }, [qualite, filtre])
  useEffect(charger, [charger])

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!fiche) return
    setErreur('')
    setEnCours(true)
    try {
      const { id, contacts: _contacts, ...corps } = fiche
      await api(id ? `/tiers/${id}/` : '/tiers/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(corps) })
      setFiche(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const champ = (nom: 'code' | 'raison_sociale' | 'numero_contribuable' | 'telephone' | 'email' | 'ville' | 'adresse') =>
    ({ value: fiche?.[nom] ?? '', onChange: (e: { target: { value: string } }) => setFiche((f) => f && { ...f, [nom]: e.target.value }) })
  const autre = qualite === 'client' ? 'est_fournisseur' : 'est_client'

  if (fiche) {
    return (
      <form className="fiche" onSubmit={enregistrer}>
        <p><a href={`#${mots.base}`} onClick={() => setFiche(null)}>← {mots.titre}</a></p>
        <h2>{fiche.id ? fiche.raison_sociale : mots.nouveau}</h2>
        <fieldset>
          <div className="grille">
            <label>Raison sociale<input required maxLength={200} autoFocus {...champ('raison_sociale')} /></label>
            <label>Code<input maxLength={20} required={!!fiche.id} placeholder={fiche.id ? '' : 'Automatique si vide'} {...champ('code')} /></label>
            <label>N° contribuable<input maxLength={50} {...champ('numero_contribuable')} /></label>
            <label>Téléphone<input maxLength={30} {...champ('telephone')} /></label>
            <label>E-mail<input type="email" {...champ('email')} /></label>
            <label>Ville<input maxLength={100} {...champ('ville')} /></label>
          </div>
          <label>Adresse<textarea rows={2} {...champ('adresse')} /></label>
          <label className="case"><input type="checkbox" checked={fiche[autre]} onChange={(e) => setFiche({ ...fiche, [autre]: e.target.checked })} /> {mots.autre}</label>
          {fiche.id && <label className="case"><input type="checkbox" checked={fiche.actif} onChange={(e) => setFiche({ ...fiche, actif: e.target.checked })} /> Actif (décoché : n'est plus proposé dans les listes)</label>}
        </fieldset>
        {fiche.id
          ? <Contacts tiers={fiche.id} depart={fiche.contacts ?? []} />
          : <p className="aide">Les contacts s'ajoutent une fois la fiche enregistrée.</p>}
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <div className="actions">
          <button type="button" className="secondaire" onClick={() => { setFiche(null); setErreur(''); charger() }}>Annuler</button>
          <button disabled={enCours}>{enCours ? 'Enregistrement…' : 'Enregistrer'}</button>
        </div>
      </form>
    )
  }

  return (
    <>
      <div className="barre">
        <h2>{mots.titre}</h2>
        {peutCreer && (
          <div className="actions">
            <a className="bouton secondaire" href={`#${mots.base}/import`}>Importer depuis Excel</a>
            <button onClick={() => { setErreur(''); setFiche(vide(qualite)) }}>{mots.nouveau}</button>
          </div>
        )}
      </div>
      <div className="grille filtres">
        <label>Recherche<input placeholder="Nom, code, ville, n° contribuable" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>Situation
          <select value={filtre.actif} onChange={(e) => setFiltre({ ...filtre, actif: e.target.value })}><option value="true">Actifs</option><option value="false">Désactivés</option><option value="">Tous</option></select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucun {mots.un}.</p>}
      {liste && liste.length > 0 && (
        <>
          <p className="aide">{total} {mots.un}{total > 1 ? 's' : ''}{total > liste.length ? ` · les ${liste.length} premiers sont affichés, précisez la recherche` : ''}</p>
          <div className="defilant">
            <table>
              <thead><tr><th>Code</th><th>Raison sociale</th><th>Ville</th><th>Téléphone</th><th>E-mail</th><th>N° contribuable</th><th></th></tr></thead>
              <tbody>
                {liste.map((t) => (
                  <tr key={t.id}>
                    <td>{t.code}</td>
                    <td>{t.raison_sociale}{!t.actif && <> <span className="pastille">Désactivé</span></>}</td>
                    <td>{t.ville}</td><td>{t.telephone}</td><td>{t.email}</td><td>{t.numero_contribuable}</td>
                    <td>{peutModifier && <button className="secondaire" onClick={() => { setErreur(''); setFiche(t) }}>Modifier</button>}</td>
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

const CONTACT_VIDE = { nom: '', fonction: '', telephone: '', email: '' }

/** Les personnes à joindre chez le tiers. Chaque ajout, modification ou retrait est enregistré aussitôt. */
function Contacts({ tiers, depart }: { tiers: number; depart: Contact[] }) {
  const [liste, setListe] = useState(depart)
  const [saisie, setSaisie] = useState<typeof CONTACT_VIDE & { id?: number }>(CONTACT_VIDE)
  const [erreur, setErreur] = useState('')

  async function valider() {
    if (!saisie.nom.trim()) return setErreur('Indiquez le nom du contact.')
    setErreur('')
    try {
      const { id, ...corps } = saisie
      const c = await api<Contact>(id ? `/contacts/${id}/` : '/contacts/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify({ ...corps, tiers }) })
      setListe((l) => (id ? l.map((x) => (x.id === id ? c : x)) : [...l, c]))
      setSaisie(CONTACT_VIDE)
    } catch (err) {
      setErreur((err as Error).message)
    }
  }
  async function retirer(c: Contact) {
    if (!window.confirm(`Retirer ${c.nom} des contacts ?`)) return
    try {
      await api(`/contacts/${c.id}/`, { method: 'DELETE' })
      setListe((l) => l.filter((x) => x.id !== c.id))
    } catch (err) {
      setErreur((err as Error).message)
    }
  }
  const champ = (nom: keyof typeof CONTACT_VIDE) => ({ value: saisie[nom], onChange: (e: { target: { value: string } }) => setSaisie({ ...saisie, [nom]: e.target.value }) })

  return (
    <fieldset>
      <legend>Contacts</legend>
      {liste.length === 0 && <p className="aide">Aucun contact.</p>}
      {liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Nom</th><th>Fonction</th><th>Téléphone</th><th>E-mail</th><th></th></tr></thead>
            <tbody>
              {liste.map((c) => (
                <tr key={c.id}>
                  <td>{c.nom}</td><td>{c.fonction}</td><td>{c.telephone}</td><td>{c.email}</td>
                  <td>
                    <button type="button" className="secondaire" onClick={() => setSaisie(c)}>Modifier</button>{' '}
                    <button type="button" className="secondaire" onClick={() => retirer(c)}>Retirer</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="grille">
        <label>Nom<input maxLength={150} aria-label="Nom du contact" {...champ('nom')} /></label>
        <label>Fonction<input maxLength={100} aria-label="Fonction du contact" {...champ('fonction')} /></label>
        <label>Téléphone<input maxLength={30} aria-label="Téléphone du contact" {...champ('telephone')} /></label>
        <label>E-mail<input type="email" aria-label="E-mail du contact" {...champ('email')} /></label>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        {saisie.id && <button type="button" className="secondaire" onClick={() => setSaisie(CONTACT_VIDE)}>Annuler la modification</button>}
        <button type="button" className="secondaire" onClick={valider}>{saisie.id ? 'Enregistrer le contact' : 'Ajouter le contact'}</button>
      </div>
    </fieldset>
  )
}

/** Fournisseurs ou clients depuis un classeur Excel. On contrôle d'abord, on importe ensuite. */
export function ImportTiers({ qualite }: { qualite: Qualite }) {
  const mots = MOTS[qualite]
  const [bilan, setBilan] = useState<Bilan | null>(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const fichier = useRef<HTMLInputElement>(null)

  async function envoyer(simuler: boolean, e?: FormEvent) {
    e?.preventDefault()
    const f = fichier.current?.files?.[0]
    if (!f) return setErreur('Choisissez le fichier.')
    const corps = new FormData()
    corps.set('fichier', f)
    corps.set('qualite', qualite)
    if (simuler) corps.set('simuler', '1')
    setErreur('')
    setEnCours(true)
    try {
      setBilan(await api<Bilan>('/tiers/importer/', { method: 'POST', body: corps }))
    } catch (err) {
      setBilan(null)
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const pret = bilan?.simulation && bilan.erreurs.length === 0 && bilan.lues > 0
  return (
    <form className="fiche" onSubmit={(e) => envoyer(true, e)}>
      <p><a href={`#${mots.base}`}>← {mots.titre}</a></p>
      <h2>Importer les {mots.un}s depuis Excel</h2>
      <fieldset>
        <p className="aide">
          Première feuille du classeur, titres en première ligne : <strong>Raison sociale</strong>, puis au besoin
          Code, N° contribuable, Téléphone, E-mail, Adresse, Ville.
          Une fiche déjà connue (même code, ou à défaut même raison sociale) est mise à jour (une case vide ne change rien), les autres sont créées.
          Sans code, un numéro est attribué automatiquement.
        </p>
        <label>Classeur Excel (.xlsx)
          <input ref={fichier} type="file" accept=".xlsx" required onChange={() => setBilan(null)} />
        </label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {bilan && (
        <fieldset>
          <legend>{bilan.ecrit ? 'Import terminé' : bilan.erreurs.length ? 'Fichier à corriger : rien n\'a été importé' : 'Contrôle réussi'}</legend>
          <p role="status">
            {bilan.lues} ligne(s) lue(s) · {bilan.crees} {mots.un}(s) {bilan.ecrit ? 'créé(s)' : 'à créer'} ·{' '}
            {bilan.modifies} {bilan.ecrit ? 'modifié(s)' : 'à modifier'} · {bilan.inchanges} inchangé(s)
          </p>
          {bilan.erreurs.length > 0 && <ul>{bilan.erreurs.map((x) => <li key={x} className="erreur">{x}</li>)}</ul>}
        </fieldset>
      )}
      <div className="actions">
        <button className={pret ? 'secondaire' : ''} disabled={enCours}>{enCours ? 'Lecture…' : 'Contrôler le fichier'}</button>
        {pret && <button type="button" disabled={enCours} onClick={() => envoyer(false)}>Importer</button>}
      </div>
    </form>
  )
}
