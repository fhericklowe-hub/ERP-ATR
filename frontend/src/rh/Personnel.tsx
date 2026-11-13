import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Site } from '../api'
import PiecesJointes from '../PiecesJointes'
import { dateFr } from '../achats/types'

type Contrat = { id: number; salarie: number; type: string; type_libelle: string; date_debut: string; date_fin: string | null; fin_essai: string | null; fonction: string; observations: string }
type Piece = { id: number; salarie: number; type: string; type_libelle: string; libelle: string; numero: string; date_delivrance: string | null; date_expiration: string | null }
type Salarie = {
  id: number; matricule: string; statut: string; statut_libelle: string; nom: string; prenoms: string; nom_complet: string; sexe: string
  date_naissance: string | null; lieu_naissance: string; nationalite: string; situation_familiale: string; situation_libelle: string; enfants: number
  telephone: string; email: string; adresse: string; contact_urgence: string; telephone_urgence: string; numero_cnps: string
  site: number | ''; site_nom: string; service: number | null; service_nom: string; fonction: string; categorie: string; categorie_libelle: string
  responsable: number | null; responsable_nom: string; utilisateur: number | null; utilisateur_nom: string; date_embauche: string | null
  date_sortie: string | null; motif_sortie: string; observations: string; anciennete: number | null; contrat: string
  contrats: Contrat[]; pieces: Piece[]; peut_modifier: boolean; peut_sortir: boolean
}
type Echeance = { salarie: number; salarie_nom: string; matricule: string; genre: string; libelle: string; date: string; jours: number }
type Service = { id: number; nom: string }
type Compte = { id: number; username: string; first_name: string; last_name: string }
type Saisie = Pick<Salarie, 'matricule' | 'nom' | 'prenoms' | 'sexe' | 'date_naissance' | 'lieu_naissance' | 'nationalite' | 'situation_familiale' | 'enfants'
  | 'telephone' | 'email' | 'adresse' | 'contact_urgence' | 'telephone_urgence' | 'numero_cnps' | 'site' | 'service' | 'fonction' | 'categorie'
  | 'responsable' | 'utilisateur' | 'date_embauche' | 'observations'>

const CATEGORIES = [['', 'Non précisée'], ['CADRE', 'Cadre'], ['MAITRISE', 'Agent de maîtrise'], ['EMPLOYE', 'Employé'], ['OUVRIER', 'Ouvrier']]
const SITUATIONS = [['', 'Non précisée'], ['CELIB', 'Célibataire'], ['MARIE', 'Marié(e)'], ['DIVORCE', 'Divorcé(e)'], ['VEUF', 'Veuf ou veuve']]
const CONTRATS = [['CDI', 'CDI'], ['CDD', 'CDD'], ['STAGE', 'Stage'], ['JOURNALIER', 'Journalier'], ['PRESTA', 'Prestataire ou intérimaire']]
const PIECES = [['PERMIS', 'Permis de conduire'], ['CONDUITE', "Autorisation de conduite d'engins"], ['MEDICALE', 'Visite médicale'], ['HABILIT', 'Habilitation ou certificat'],
  ['IDENTITE', "Pièce d'identité"], ['SEJOUR', 'Carte de séjour'], ['DIPLOME', 'Diplôme'], ['AUTRE', 'Autre']]
const aujourdhui = () => new Date().toLocaleDateString('fr-CA')
const delai = (jours: number) => (jours < 0 ? `dépassé depuis ${-jours} j` : jours === 0 ? "aujourd'hui" : `dans ${jours} j`)
const joursAvant = (date: string | null) => (date ? Math.round((new Date(date).getTime() - new Date(aujourdhui()).getTime()) / 86400000) : null)

function useListes() {
  const [sites, setSites] = useState<Site[]>([])
  const [services, setServices] = useState<Service[]>([])
  useEffect(() => {
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    api<Page<Service>>('/services/?actif=true&page_size=100').then((p) => setServices(p.results)).catch(() => undefined)
  }, [])
  return { sites, services }
}

export function ListeSalaries({ peutCreer }: { peutCreer: boolean }) {
  const [liste, setListe] = useState<Salarie[] | null>(null)
  const [total, setTotal] = useState(0)
  const [filtre, setFiltre] = useState({ search: '', site: '', service: '', statut: 'ACTIF' })
  const [erreur, setErreur] = useState('')
  const { sites, services } = useListes()
  useEffect(() => {
    api<Page<Salarie>>(`/rh/salaries/?${new URLSearchParams(filtre)}&page_size=200`).then((p) => { setListe(p.results); setTotal(p.count) }).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  return (
    <>
      <div className="barre">
        <h2>Personnel</h2>
        {peutCreer && <div className="actions"><a className="bouton" href="#/personnel/nouveau">Nouveau salarié</a></div>}
      </div>
      <div className="grille filtres large">
        <label>Recherche<input placeholder="Nom, matricule, fonction" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>Site
          <select value={filtre.site} onChange={(e) => setFiltre({ ...filtre, site: e.target.value })}><option value="">Tous</option>{sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select>
        </label>
        <label>Service
          <select value={filtre.service} onChange={(e) => setFiltre({ ...filtre, service: e.target.value })}><option value="">Tous</option>{services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select>
        </label>
        <label>Situation
          <select value={filtre.statut} onChange={(e) => setFiltre({ ...filtre, statut: e.target.value })}><option value="ACTIF">En poste</option><option value="SORTI">Sortis des effectifs</option><option value="">Tous</option></select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucun salarié.</p>}
      {liste && liste.length > 0 && (
        <>
          <p className="aide">{total} salarié{total > 1 ? 's' : ''}</p>
          <div className="defilant">
            <table>
              <thead><tr><th>Matricule</th><th>Nom</th><th>Fonction</th><th>Site</th><th>Contrat</th><th>Embauche</th><th>Situation</th></tr></thead>
              <tbody>
                {liste.map((s) => (
                  <tr key={s.id}>
                    <td><a href={`#/personnel/${s.id}`}>{s.matricule}</a></td><td>{s.nom_complet}</td>
                    <td>{s.fonction}{s.service_nom && <><br /><span className="aide">{s.service_nom}</span></>}</td><td>{s.site_nom}</td>
                    <td>{s.contrat}</td><td>{s.date_embauche ? dateFr(s.date_embauche) : ''}</td>
                    <td><span className={`pastille ${s.statut === 'ACTIF' ? 'complete' : ''}`}>{s.statut_libelle}</span></td>
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

const vide = (): Saisie => ({
  matricule: '', nom: '', prenoms: '', sexe: '', date_naissance: null, lieu_naissance: '', nationalite: '', situation_familiale: '', enfants: 0,
  telephone: '', email: '', adresse: '', contact_urgence: '', telephone_urgence: '', numero_cnps: '', site: '', service: null, fonction: '', categorie: '',
  responsable: null, utilisateur: null, date_embauche: null, observations: '',
})

export function FormulaireSalarie({ id }: { id?: number }) {
  const [s, setS] = useState<Saisie>(vide)
  const [collegues, setCollegues] = useState<Salarie[]>([])
  const [comptes, setComptes] = useState<Compte[]>([])
  const [pret, setPret] = useState(!id)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const { sites, services } = useListes()
  useEffect(() => {
    api<Page<Salarie>>('/rh/salaries/?statut=ACTIF&page_size=200').then((p) => setCollegues(p.results)).catch(() => undefined)
    api<Page<Compte>>('/utilisateurs/?is_active=true&page_size=200').then((p) => setComptes(p.results)).catch(() => undefined)
    if (id) api<Salarie>(`/rh/salaries/${id}/`).then((x) => { setS(Object.fromEntries(Object.keys(vide()).map((k) => [k, x[k as keyof Saisie]])) as Saisie); setPret(true) }).catch((e: Error) => setErreur(e.message))
  }, [id])

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const r = await api<Salarie>(id ? `/rh/salaries/${id}/` : '/rh/salaries/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(s) })
      location.hash = `#/personnel/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setS((x) => ({ ...x, [k]: v }))
  const texte = (k: 'matricule' | 'nom' | 'prenoms' | 'lieu_naissance' | 'nationalite' | 'telephone' | 'email' | 'adresse' | 'contact_urgence' | 'telephone_urgence' | 'numero_cnps' | 'fonction', libelle: string, requis = false, type = 'text') => (
    <label>{libelle}<input type={type} required={requis} value={s[k]} onChange={(e) => champ(k, e.target.value)} /></label>
  )
  const date = (k: 'date_naissance' | 'date_embauche', libelle: string) => (
    <label>{libelle}<input type="date" max={aujourdhui()} value={s[k] ?? ''} onChange={(e) => champ(k, e.target.value || null)} /></label>
  )
  if (!pret) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  return (
    <form className="fiche" onSubmit={enregistrer}>
      <p><a href={id ? `#/personnel/${id}` : '#/personnel'}>← Retour</a></p>
      <h2>{id ? 'Modifier le dossier' : 'Nouveau salarié'}</h2>
      <fieldset>
        <legend>État civil</legend>
        <div className="grille">
          {texte('nom', 'Nom', true)}{texte('prenoms', 'Prénoms', true)}
          <label>Sexe<select value={s.sexe} onChange={(e) => champ('sexe', e.target.value)}><option value="">Non précisé</option><option value="M">Homme</option><option value="F">Femme</option></select></label>
          {date('date_naissance', 'Date de naissance')}{texte('lieu_naissance', 'Lieu de naissance')}{texte('nationalite', 'Nationalité')}
          <label>Situation familiale<select value={s.situation_familiale} onChange={(e) => champ('situation_familiale', e.target.value)}>{SITUATIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label>Enfants à charge<input type="number" min="0" max="30" value={s.enfants} onChange={(e) => champ('enfants', Number(e.target.value))} /></label>
          {texte('numero_cnps', 'N° CNPS')}
        </div>
      </fieldset>
      <fieldset>
        <legend>Coordonnées</legend>
        <div className="grille">
          {texte('telephone', 'Téléphone')}{texte('email', 'E-mail', false, 'email')}{texte('adresse', 'Adresse')}
          {texte('contact_urgence', 'Personne à prévenir')}{texte('telephone_urgence', 'Son téléphone')}
        </div>
      </fieldset>
      <fieldset>
        <legend>Poste</legend>
        <div className="grille">
          <label>Matricule<input maxLength={20} placeholder="Automatique si vide" value={s.matricule} onChange={(e) => champ('matricule', e.target.value)} /></label>
          {texte('fonction', 'Fonction')}
          <label>Catégorie<select value={s.categorie} onChange={(e) => champ('categorie', e.target.value)}>{CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label>Site<select required value={s.site} onChange={(e) => champ('site', Number(e.target.value))}><option value="">Choisir</option>{sites.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}</select></label>
          <label>Service<select value={s.service ?? ''} onChange={(e) => champ('service', Number(e.target.value) || null)}><option value="">Aucun</option>{services.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}</select></label>
          <label>Responsable hiérarchique<select value={s.responsable ?? ''} onChange={(e) => champ('responsable', Number(e.target.value) || null)}><option value="">Aucun</option>{collegues.filter((c) => c.id !== id).map((c) => <option key={c.id} value={c.id}>{c.nom_complet}</option>)}</select></label>
          {date('date_embauche', "Date d'embauche")}
          <label>Compte dans l'ERP<select value={s.utilisateur ?? ''} onChange={(e) => champ('utilisateur', Number(e.target.value) || null)}><option value="">Aucun</option>{comptes.map((c) => <option key={c.id} value={c.id}>{[c.last_name, c.first_name].filter(Boolean).join(' ') || c.username}</option>)}</select></label>
        </div>
        <label>Observations<textarea value={s.observations} onChange={(e) => champ('observations', e.target.value)} /></label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions"><button disabled={enCours}>Enregistrer</button></div>
    </form>
  )
}

export function DetailSalarie({ id }: { id: number }) {
  const [s, setS] = useState<Salarie | null>(null)
  const [c, setC] = useState({ type: 'CDI', date_debut: '', date_fin: '', fin_essai: '', fonction: '' })
  const [p, setP] = useState({ type: 'PERMIS', libelle: '', numero: '', date_delivrance: '', date_expiration: '' })
  const [sortie, setSortie] = useState({ date_sortie: aujourdhui(), motif: '' })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const charger = useCallback(() => {
    api<Salarie>(`/rh/salaries/${id}/`).then(setS).catch((e: Error) => setErreur(e.message))
  }, [id])
  useEffect(charger, [charger])

  async function envoyer(chemin: string, methode: string, corps?: object) {
    setErreur('')
    setEnCours(true)
    try {
      await api(chemin, { method: methode, body: corps ? JSON.stringify(corps) : undefined })
      charger()
      return true
    } catch (err) {
      setErreur((err as Error).message)
      return false
    } finally {
      setEnCours(false)
    }
  }
  const vides = (o: Record<string, string>) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v === '' && k.startsWith('date') || v === '' && k === 'fin_essai' ? null : v]))
  async function ajouterContrat(e: FormEvent) {
    e.preventDefault()
    if (await envoyer('/rh/contrats/', 'POST', { salarie: id, ...vides(c) })) setC({ type: 'CDI', date_debut: '', date_fin: '', fin_essai: '', fonction: '' })
  }
  async function ajouterPiece(e: FormEvent) {
    e.preventDefault()
    if (await envoyer('/rh/pieces/', 'POST', { salarie: id, ...vides(p) })) setP({ type: 'PERMIS', libelle: '', numero: '', date_delivrance: '', date_expiration: '' })
  }

  if (!s) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  return (
    <div className="fiche">
      <p><a href="#/personnel">← Personnel</a></p>
      <div className="barre">
        <h2>{s.nom_complet}</h2>
        {s.peut_modifier && <div className="actions"><a className="bouton secondaire" href={`#/personnel/${id}/modifier`}>Modifier</a></div>}
      </div>
      <p className="statut">{s.statut_libelle}{s.contrat && ` · ${s.contrat}`}</p>
      <dl>
        <dt>Matricule</dt><dd>{s.matricule}</dd>
        <dt>Poste</dt><dd>{[s.fonction, s.categorie_libelle, s.service_nom, s.site_nom].filter(Boolean).join(' · ')}</dd>
        {s.responsable_nom && <><dt>Responsable</dt><dd><a href={`#/personnel/${s.responsable}`}>{s.responsable_nom}</a></dd></>}
        {s.date_embauche && <><dt>Embauche</dt><dd>le {dateFr(s.date_embauche)}{s.anciennete !== null && ` · ${s.anciennete} an${s.anciennete > 1 ? 's' : ''} d'ancienneté`}</dd></>}
        {s.date_sortie && <><dt>Sortie</dt><dd>le {dateFr(s.date_sortie)} · {s.motif_sortie}</dd></>}
        {(s.date_naissance || s.lieu_naissance) && <><dt>Naissance</dt><dd>{[s.date_naissance && `le ${dateFr(s.date_naissance)}`, s.lieu_naissance && `à ${s.lieu_naissance}`].filter(Boolean).join(' ')}</dd></>}
        {(s.nationalite || s.situation_libelle) && <><dt>État civil</dt><dd>{[s.nationalite, s.situation_libelle, s.enfants ? `${s.enfants} enfant${s.enfants > 1 ? 's' : ''} à charge` : ''].filter(Boolean).join(' · ')}</dd></>}
        {(s.telephone || s.email || s.adresse) && <><dt>Coordonnées</dt><dd>{[s.telephone, s.email, s.adresse].filter(Boolean).join(' · ')}</dd></>}
        {s.contact_urgence && <><dt>À prévenir</dt><dd>{[s.contact_urgence, s.telephone_urgence].filter(Boolean).join(' · ')}</dd></>}
        {s.numero_cnps && <><dt>N° CNPS</dt><dd>{s.numero_cnps}</dd></>}
        {s.utilisateur_nom && <><dt>Compte ERP</dt><dd>{s.utilisateur_nom}</dd></>}
        {s.observations && <><dt>Observations</dt><dd style={{ whiteSpace: 'pre-line' }}>{s.observations}</dd></>}
      </dl>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      <fieldset>
        <legend>Contrats</legend>
        {s.contrats.length === 0 && <p className="aide">Aucun contrat saisi.</p>}
        {s.contrats.length > 0 && (
          <div className="defilant"><table>
            <thead><tr><th>Type</th><th>Début</th><th>Fin</th><th>Fin d'essai</th><th>Fonction</th><th></th></tr></thead>
            <tbody>{s.contrats.map((x) => (
              <tr key={x.id}><td>{x.type_libelle}</td><td>{dateFr(x.date_debut)}</td><td>{x.date_fin ? dateFr(x.date_fin) : 'sans terme'}</td><td>{x.fin_essai ? dateFr(x.fin_essai) : ''}</td><td>{x.fonction}</td>
                <td>{s.peut_modifier && <button type="button" className="lien" disabled={enCours} onClick={() => confirm('Supprimer ce contrat ?') && envoyer(`/rh/contrats/${x.id}/`, 'DELETE')}>Supprimer</button>}</td></tr>
            ))}</tbody>
          </table></div>
        )}
        {s.peut_modifier && (
          <form className="grille" onSubmit={ajouterContrat}>
            <label>Type<select value={c.type} onChange={(e) => setC({ ...c, type: e.target.value })}>{CONTRATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Début<input type="date" required value={c.date_debut} onChange={(e) => setC({ ...c, date_debut: e.target.value })} /></label>
            <label>Fin (vide si sans terme)<input type="date" min={c.date_debut} value={c.date_fin} onChange={(e) => setC({ ...c, date_fin: e.target.value })} /></label>
            <label>Fin de la période d'essai<input type="date" min={c.date_debut} value={c.fin_essai} onChange={(e) => setC({ ...c, fin_essai: e.target.value })} /></label>
            <label>Fonction<input maxLength={100} value={c.fonction} onChange={(e) => setC({ ...c, fonction: e.target.value })} /></label>
            <div className="actions"><button className="secondaire" disabled={enCours}>Ajouter le contrat</button></div>
          </form>
        )}
      </fieldset>

      <fieldset>
        <legend>Permis, habilitations et visites</legend>
        {s.pieces.length === 0 && <p className="aide">Aucune pièce saisie.</p>}
        {s.pieces.length > 0 && (
          <div className="defilant"><table>
            <thead><tr><th>Pièce</th><th>Numéro</th><th>Délivré le</th><th>Valable jusqu'au</th><th></th></tr></thead>
            <tbody>{s.pieces.map((x) => {
              const j = joursAvant(x.date_expiration)
              return (
                <tr key={x.id}><td>{x.type_libelle}{x.libelle && ` · ${x.libelle}`}</td><td>{x.numero}</td><td>{x.date_delivrance ? dateFr(x.date_delivrance) : ''}</td>
                  <td>{x.date_expiration ? <>{dateFr(x.date_expiration)} {j !== null && j <= 30 && <span className={`pastille ${j < 0 ? 'u1' : 'partielle'}`}>{delai(j)}</span>}</> : ''}</td>
                  <td>{s.peut_modifier && <button type="button" className="lien" disabled={enCours} onClick={() => confirm('Supprimer cette pièce ?') && envoyer(`/rh/pieces/${x.id}/`, 'DELETE')}>Supprimer</button>}</td></tr>
              )
            })}</tbody>
          </table></div>
        )}
        {s.peut_modifier && (
          <form className="grille" onSubmit={ajouterPiece}>
            <label>Pièce<select value={p.type} onChange={(e) => setP({ ...p, type: e.target.value })}>{PIECES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Précision<input maxLength={120} placeholder="Catégorie, type d'engin, organisme" value={p.libelle} onChange={(e) => setP({ ...p, libelle: e.target.value })} /></label>
            <label>Numéro<input maxLength={60} value={p.numero} onChange={(e) => setP({ ...p, numero: e.target.value })} /></label>
            <label>Délivré le<input type="date" max={aujourdhui()} value={p.date_delivrance} onChange={(e) => setP({ ...p, date_delivrance: e.target.value })} /></label>
            <label>Valable jusqu'au<input type="date" value={p.date_expiration} onChange={(e) => setP({ ...p, date_expiration: e.target.value })} /></label>
            <div className="actions"><button className="secondaire" disabled={enCours}>Ajouter la pièce</button></div>
          </form>
        )}
      </fieldset>

      {s.peut_sortir && s.statut === 'ACTIF' && (
        <fieldset>
          <legend>Sortie des effectifs</legend>
          <div className="grille">
            <label>Date de sortie<input type="date" value={sortie.date_sortie} onChange={(e) => setSortie({ ...sortie, date_sortie: e.target.value })} /></label>
            <label>Motif<input maxLength={200} placeholder="Démission, fin de contrat, licenciement, retraite…" value={sortie.motif} onChange={(e) => setSortie({ ...sortie, motif: e.target.value })} /></label>
          </div>
          <div className="actions"><button className="danger" disabled={enCours} onClick={() => envoyer(`/rh/salaries/${id}/sortir/`, 'POST', sortie)}>Enregistrer la sortie</button></div>
        </fieldset>
      )}
      {s.peut_sortir && s.statut === 'SORTI' && <div className="actions"><button className="secondaire" disabled={enCours} onClick={() => envoyer(`/rh/salaries/${id}/reintegrer/`, 'POST', {})}>Remettre en poste</button></div>}
      <PiecesJointes modele="rh.salarie" objet={id} aide="Joignez ici les copies : contrat signé, pièce d'identité, permis, certificats." />
    </div>
  )
}

export function EcheancesPersonnel() {
  const [liste, setListe] = useState<Echeance[] | null>(null)
  const [jours, setJours] = useState('30')
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Echeance[]>(`/rh/salaries/echeances/?jours=${jours}`).then(setListe).catch((e: Error) => setErreur(e.message))
  }, [jours])
  return (
    <>
      <div className="barre"><h2>Échéances du personnel</h2></div>
      <p className="aide">Permis, autorisations de conduite, visites médicales et pièces à renouveler, fins de contrat et de période d'essai des salariés en poste.</p>
      <div className="grille filtres">
        <label>Horizon
          <select value={jours} onChange={(e) => setJours(e.target.value)}><option value="30">30 jours</option><option value="60">60 jours</option><option value="90">90 jours</option><option value="180">6 mois</option></select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Rien n'arrive à échéance sur cette période.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Salarié</th><th>Échéance</th><th>Date</th><th></th></tr></thead>
            <tbody>
              {liste.map((e, i) => (
                <tr key={i}>
                  <td><a href={`#/personnel/${e.salarie}`}>{e.salarie_nom}</a><br /><span className="aide">{e.matricule}</span></td>
                  <td>{e.libelle}</td><td>{dateFr(e.date)}</td>
                  <td><span className={`pastille ${e.jours < 0 ? 'u1' : e.jours <= 7 ? 'partielle' : ''}`}>{delai(e.jours)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
