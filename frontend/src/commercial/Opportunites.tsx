import ChoixListe from '../ChoixListe'
import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, apiTout, type Page, type Site, type Tiers } from '../api'
import BoutonExcel from '../BoutonExcel'
import { montant } from '../achats/commandes'
import { dateHeureFr } from '../achats/types'

type Decision = { id: number; date: string; auteur_nom: string; action: string; niveau: string; niveau_libelle: string; commentaire: string; statut_libelle: string }
type Fiche = {
  id: number; numero: string; statut: string; statut_libelle: string; nom_affaire: string; client: number | ''; client_nom: string
  site: number | ''; site_nom: string; commercial_nom: string; activite: string; activite_libelle: string; type_affaire: string; type_affaire_libelle: string
  origine: string; origine_libelle: string; phase: string; phase_libelle: string; probabilite: number | null; devise: string
  ca_previsionnel: string; marge_previsionnelle: string; taux_marge: string | null; ca_services: string | null; marge_services: string | null
  ca_materiel: string | null; marge_materiel: string | null; lieu: string; date_prise_commande: string | null; prochaine_etape: string
  reference_ao: string; date_lancement_ao: string | null; date_limite_ao: string | null; partenaire: string; part_partenaire: string | null
  risques: string; observations: string; decisions: Decision[]; devis: { id: number; numero: string; statut_libelle: string }[]
  modifiable: boolean; peut_preparer: boolean; peut_decider: boolean; peut_annuler: boolean
}
type Saisie = Pick<Fiche, 'nom_affaire' | 'client' | 'site' | 'activite' | 'type_affaire' | 'origine' | 'phase' | 'probabilite' | 'devise' | 'ca_previsionnel'
  | 'marge_previsionnelle' | 'ca_services' | 'marge_services' | 'ca_materiel' | 'marge_materiel' | 'lieu' | 'date_prise_commande' | 'prochaine_etape'
  | 'reference_ao' | 'date_lancement_ao' | 'date_limite_ao' | 'partenaire' | 'part_partenaire' | 'risques' | 'observations'>

const STATUTS = [['', 'Toutes'], ['BROUILLON', 'Brouillons'], ['ATT_RESP', 'Attente responsable commercial'], ['ATT_FIN', 'Attente finance'],
  ['ATT_DG', 'Attente DG'], ['GO', 'GO'], ['NO_GO', 'NO GO'], ['ANNULEE', 'Annulées']]
const TYPES = [['LOCATION', 'Location de matériel'], ['TRANSPORT', 'Transport'], ['PRESTATION', 'Prestation (manutention, levage…)'], ['VENTE', 'Vente'], ['AUTRE', 'Autre']]
const ORIGINES = [['APPEL_OFFRES', "Appel d'offres"], ['CLIENT', 'Client existant'], ['PROSPECTION', 'Prospection'], ['RECOMMANDATION', 'Recommandation'], ['AUTRE', 'Autre']]
const PHASES = [['IDENTIFICATION', 'Identification'], ['QUALIFICATION', 'Qualification'], ['OFFRE', 'Offre à remettre'], ['NEGOCIATION', 'Négociation']]
const ACTIVITES = [['', 'Non précisée'], ['MANUTENTION', 'Manutention'], ['LEVAGE', 'Levage'], ['TRANSPORT', 'Transport'], ['AUTRE', 'Autre']]
const DEVISES = [['XOF', 'Franc CFA (XOF)'], ['EUR', 'Euro (EUR)'], ['USD', 'Dollar US (USD)']]
const ACTIONS: Record<string, string> = { SOUMIS: 'a soumis la fiche', VALIDE: 'a validé', REFUSE: 'a prononcé le NO GO', RENVOYE: 'a renvoyé la fiche', ANNULE: 'a annulé la fiche' }
const pastille = (s: string) => (s === 'GO' ? 'complete' : s === 'NO_GO' || s === 'ANNULEE' ? 'u1' : s === 'BROUILLON' ? '' : 'partielle')
const vide = (): Saisie => ({
  nom_affaire: '', client: '', site: '', activite: '', type_affaire: 'LOCATION', origine: 'CLIENT', phase: 'QUALIFICATION', probabilite: null, devise: 'XOF',
  ca_previsionnel: '', marge_previsionnelle: '', ca_services: null, marge_services: null, ca_materiel: null, marge_materiel: null, lieu: '',
  date_prise_commande: null, prochaine_etape: '', reference_ao: '', date_lancement_ao: null, date_limite_ao: null, partenaire: '', part_partenaire: null, risques: '', observations: '',
})
const sansVide = (v: string | null) => (v === '' ? null : v)

export function ListeOpportunites() {
  const [liste, setListe] = useState<Fiche[] | null>(null)
  const [filtre, setFiltre] = useState({ search: '', statut: '' })
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    apiTout<Fiche>(`/commercial/opportunites/?${new URLSearchParams(filtre)}`).then((p) => setListe(p)).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  return (
    <>
      <div className="barre">
        <h2>Fiches GO / NO GO</h2>
        <div className="actions">
          <BoutonExcel chemin="/commercial/opportunites/" nom="go-no-go" filtres={filtre} onErreur={setErreur} />
          <a className="bouton" href="#/opportunites/nouvelle">Nouvelle fiche</a>
        </div>
      </div>
      <p className="aide">Avant de faire un devis, chaque opportunité se valide : responsable commercial, puis finance, puis DG. Le devis se fait une fois le GO obtenu.</p>
      <div className="grille filtres">
        <label>Recherche<input placeholder="N°, affaire, client" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>Statut
          <select value={filtre.statut} onChange={(e) => setFiltre({ ...filtre, statut: e.target.value })}>{STATUTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucune fiche.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Affaire</th><th>Client</th><th>Commercial</th><th className="nombre">CA prévisionnel</th><th className="nombre">Marge</th><th>Statut</th></tr></thead>
            <tbody>
              {liste.map((f) => (
                <tr key={f.id}>
                  <td><a href={`#/opportunites/${f.id}`}>{f.numero}</a></td>
                  <td>{f.nom_affaire}<br /><span className="aide">{f.type_affaire_libelle}</span></td>
                  <td>{f.client_nom}</td>
                  <td>{f.commercial_nom}</td>
                  <td className="nombre">{montant(f.ca_previsionnel, f.devise)} {f.devise}</td>
                  <td className="nombre">{f.taux_marge !== null && `${Number(f.taux_marge).toLocaleString('fr-FR')} %`}</td>
                  <td><span className={`pastille ${pastille(f.statut)}`}>{f.statut_libelle}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export default function FicheOpportunite({ id }: { id?: number }) {
  const [f, setF] = useState<Fiche | null>(null)
  const [d, setD] = useState<Saisie>(vide())
  const [clients, setClients] = useState<Tiers[]>([])
  const [sites, setSites] = useState<Site[]>([])
  const [texte, setTexte] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    if (!id) return
    api<Fiche>(`/commercial/opportunites/${id}/`).then((x) => { setF(x); setD({ ...vide(), ...x }) }).catch((e: Error) => setErreur(e.message))
  }, [id])
  useEffect(charger, [charger])
  useEffect(() => {
    apiTout<Tiers>('/tiers/?est_client=true&actif=true').then((p) => setClients(p)).catch(() => undefined)
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
  }, [])

  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setD((x) => ({ ...x, [k]: v }))
  const nombre = (k: 'ca_services' | 'marge_services' | 'ca_materiel' | 'marge_materiel' | 'part_partenaire') => (e: { target: { value: string } }) => champ(k, e.target.value === '' ? null : e.target.value)
  const taux = Number(d.ca_previsionnel) > 0 ? Math.round((Number(d.marge_previsionnelle || 0) / Number(d.ca_previsionnel)) * 1000) / 10 : null
  const editable = !id || (f?.modifiable && f.peut_preparer)

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const corps = { ...d, date_prise_commande: sansVide(d.date_prise_commande), date_lancement_ao: sansVide(d.date_lancement_ao), date_limite_ao: sansVide(d.date_limite_ao) }
      const x = await api<Fiche>(id ? `/commercial/opportunites/${id}/` : '/commercial/opportunites/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(corps) })
      if (id) { setF(x); setD({ ...vide(), ...x }) } else location.hash = `#/opportunites/${x.id}`
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  async function agir(nom: string) {
    setErreur('')
    setEnCours(true)
    try {
      const x = await api<Fiche>(`/commercial/opportunites/${id}/${nom}/`, { method: 'POST', body: JSON.stringify({ commentaire: texte }) })
      setF(x)
      setD({ ...vide(), ...x })
      setTexte('')
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const suite = f && (f.peut_decider || f.peut_annuler || (f.modifiable && f.peut_preparer))
  return (
    <div className="fiche">
      <p><a href="#/opportunites">← Fiches GO / NO GO</a></p>
      <div className="barre">
        <h2>{f ? `Fiche ${f.numero}` : 'Nouvelle fiche GO / NO GO'}</h2>
        {f?.statut === 'GO' && <a className="bouton" href={`#/devis/nouveau?opportunite=${f.id}`}>Établir le devis</a>}
      </div>
      {f && <p><span className={`pastille ${pastille(f.statut)}`}>{f.statut_libelle}</span> · {f.commercial_nom}
        {f.devis.length > 0 && <> · devis : {f.devis.map((x, i) => <span key={x.id}>{i > 0 && ', '}<a href={`#/devis/${x.id}`}>{x.numero}</a> ({x.statut_libelle})</span>)}</>}</p>}
      <form className="fiche" onSubmit={enregistrer}>
        <fieldset disabled={!editable}>
          <legend>Affaire</legend>
          <div className="grille">
            <label>Nom de l'affaire<input required maxLength={200} value={d.nom_affaire} onChange={(e) => champ('nom_affaire', e.target.value)} /></label>
            <label>Client
              <ChoixListe required value={String(d.client)} onChange={(v) => champ('client', Number(v))} options={clients.map((c) => ({ id: c.id, libelle: `${c.raison_sociale} (${c.code})` }))} />
            </label>
            <label>Agence
              <select required value={d.site} onChange={(e) => champ('site', Number(e.target.value))}>
                <option value="">Choisir…</option>
                {sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
              </select>
            </label>
            <label>Activité<select value={d.activite} onChange={(e) => champ('activite', e.target.value)}>{ACTIVITES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Type d'affaire<select value={d.type_affaire} onChange={(e) => champ('type_affaire', e.target.value)}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Origine de l'affaire<select value={d.origine} onChange={(e) => champ('origine', e.target.value)}>{ORIGINES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Phase de vente<select value={d.phase} onChange={(e) => champ('phase', e.target.value)}>{PHASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Probabilité (%)<input type="number" min="0" max="100" value={d.probabilite ?? ''} onChange={(e) => champ('probabilite', e.target.value === '' ? null : Number(e.target.value))} /></label>
            <label>Lieu d'intervention<input maxLength={200} value={d.lieu} onChange={(e) => champ('lieu', e.target.value)} /></label>
            <label>Prise de commande prévue<input type="date" value={d.date_prise_commande ?? ''} onChange={(e) => champ('date_prise_commande', e.target.value)} /></label>
            <label>Prochaine étape<input maxLength={200} value={d.prochaine_etape} onChange={(e) => champ('prochaine_etape', e.target.value)} /></label>
          </div>
        </fieldset>
        <fieldset disabled={!editable}>
          <legend>Chiffres prévisionnels</legend>
          <div className="grille">
            <label>Devise<select value={d.devise} onChange={(e) => champ('devise', e.target.value)}>{DEVISES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>CA prévisionnel<input required type="number" min="0" step="0.01" value={d.ca_previsionnel} onChange={(e) => champ('ca_previsionnel', e.target.value)} /></label>
            <label>Marge brute prévisionnelle<input required type="number" min="0" step="0.01" value={d.marge_previsionnelle} onChange={(e) => champ('marge_previsionnelle', e.target.value)} /></label>
            <label>Taux de marge<input readOnly value={taux === null ? '' : `${taux.toLocaleString('fr-FR')} %`} /></label>
            <label>dont CA prestations<input type="number" min="0" step="0.01" value={d.ca_services ?? ''} onChange={nombre('ca_services')} /></label>
            <label>dont marge prestations<input type="number" step="0.01" value={d.marge_services ?? ''} onChange={nombre('marge_services')} /></label>
            <label>dont CA matériel / location<input type="number" min="0" step="0.01" value={d.ca_materiel ?? ''} onChange={nombre('ca_materiel')} /></label>
            <label>dont marge matériel / location<input type="number" step="0.01" value={d.marge_materiel ?? ''} onChange={nombre('marge_materiel')} /></label>
          </div>
        </fieldset>
        <fieldset disabled={!editable}>
          <legend>Appel d'offres et partenaires</legend>
          <div className="grille">
            <label>Référence de l'appel d'offres<input maxLength={100} value={d.reference_ao} onChange={(e) => champ('reference_ao', e.target.value)} /></label>
            <label>Lancement<input type="date" value={d.date_lancement_ao ?? ''} onChange={(e) => champ('date_lancement_ao', e.target.value)} /></label>
            <label>Date limite de remise<input type="date" value={d.date_limite_ao ?? ''} onChange={(e) => champ('date_limite_ao', e.target.value)} /></label>
            <label>Partenaire ou sous-traitant principal<input maxLength={150} value={d.partenaire} onChange={(e) => champ('partenaire', e.target.value)} /></label>
            <label>Part du partenaire (%)<input type="number" min="0" max="100" step="0.01" value={d.part_partenaire ?? ''} onChange={nombre('part_partenaire')} /></label>
          </div>
          <label>Risques identifiés<textarea value={d.risques} onChange={(e) => champ('risques', e.target.value)} /></label>
          <label>Observations<textarea value={d.observations} onChange={(e) => champ('observations', e.target.value)} /></label>
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        {editable && <div className="actions"><button disabled={enCours}>{id ? 'Enregistrer' : 'Enregistrer la fiche'}</button></div>}
      </form>
      {f && f.decisions.length > 0 && (
        <section aria-label="Historique">
          <h3>Validations</h3>
          <ul>
            {f.decisions.map((x) => (
              <li key={x.id}>
                {dateHeureFr(x.date)} · <strong>{x.auteur_nom}</strong> {ACTIONS[x.action] ?? x.action}{x.niveau_libelle && ` (${x.niveau_libelle})`}
                {x.commentaire && ` : « ${x.commentaire} »`}
              </li>
            ))}
          </ul>
        </section>
      )}
      {f && suite && (
        <section aria-label="Suite">
          {(f.peut_decider || f.peut_annuler || (f.modifiable && f.peut_preparer)) && (
            <label>{f.peut_decider ? 'Commentaire (obligatoire pour un NO GO ou un renvoi)' : 'Commentaire (obligatoire pour annuler)'}
              <input value={texte} onChange={(e) => setTexte(e.target.value)} />
            </label>
          )}
          <div className="actions">
            {f.modifiable && f.peut_preparer && <button disabled={enCours} onClick={() => agir('soumettre')}>Envoyer en validation</button>}
            {f.peut_decider && <button disabled={enCours} onClick={() => agir('valider')}>Valider (GO à cette étape)</button>}
            {f.peut_decider && <button className="secondaire" disabled={enCours} onClick={() => agir('renvoyer')}>Renvoyer au commercial</button>}
            {f.peut_decider && <button className="danger" disabled={enCours} onClick={() => agir('refuser')}>NO GO</button>}
            {f.peut_annuler && <button className="secondaire" disabled={enCours} onClick={() => agir('annuler')}>Annuler la fiche</button>}
          </div>
        </section>
      )}
    </div>
  )
}
