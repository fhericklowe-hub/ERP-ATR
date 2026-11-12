import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, ouvrirFichier, type Page, type Site, type Tiers } from '../api'
import PiecesJointes from '../PiecesJointes'
import { montant } from '../achats/commandes'
import { dateFr } from '../achats/types'
import { nombre } from '../stock/types'
import type { Materiel } from '../technique/types'

type Ligne = { materiel: number | null; materiel_nom?: string; designation: string; quantite: string; prix_unitaire: string; remise: string; duree: string; prix_net?: string; montant_ht?: string }
type Devis = {
  id: number; numero: string; statut: string; statut_libelle: string; expire: boolean; date: string; validite: string | null
  client: number | ''; client_nom: string; contact: string; libelle: string; activite: string; activite_libelle: string
  site: number | ''; site_nom: string; commercial_nom: string; type_loyer: string; type_loyer_libelle: string
  date_debut: string | null; date_retour: string | null; lieu: string; mode_facturation: string; mode_facturation_libelle: string
  echeance: string; mode_reglement: string; mode_reglement_libelle: string; exonere_tva: boolean; taux_tva: string; conditions: string
  reference_client: string; accepte_le: string | null; motif: string; lignes: Ligne[]
  totaux: { total_ht: string; taux_tva: string; total_tva: string; total_ttc: string; en_lettres: string }
  peut_agir: boolean; peut_gerer: boolean
}
type Saisie = Pick<Devis, 'client' | 'contact' | 'libelle' | 'activite' | 'site' | 'type_loyer' | 'date' | 'validite' | 'date_debut' | 'date_retour'
  | 'lieu' | 'mode_facturation' | 'echeance' | 'mode_reglement' | 'exonere_tva' | 'taux_tva' | 'conditions' | 'lignes'>

const STATUTS = [['', 'Tous'], ['BROUILLON', 'Brouillons'], ['ENVOYE', 'Envoyés'], ['ACCEPTE', 'Acceptés'], ['REFUSE', 'Refusés'], ['ANNULE', 'Annulés']]
const LOYERS = [['JOUR', 'Journalier', 'jours'], ['SEMAINE', 'Hebdomadaire', 'semaines'], ['MOIS', 'Mensuel', 'mois'], ['FORFAIT', 'Forfait', 'forfait']]
const FACTURATIONS = [['ECHU', 'Échu terme'], ['A_ECHOIR', 'Terme à échoir'], ['FIN', 'En fin de prestation']]
const REGLEMENTS = [['VIREMENT', 'Virement'], ['CHEQUE', 'Chèque'], ['ESPECES', 'Espèces'], ['TRAITE', 'Traite']]
const ACTIVITES = [['', 'Non précisée'], ['MANUTENTION', 'Manutention'], ['LEVAGE', 'Levage'], ['TRANSPORT', 'Transport'], ['AUTRE', 'Autre']]
const pastille = (d: Devis) => (d.statut === 'ACCEPTE' ? 'complete' : d.expire || d.statut === 'REFUSE' ? 'u1' : d.statut === 'ENVOYE' ? 'partielle' : '')
const aujourdhui = () => new Date().toLocaleDateString('fr-CA')
const ligneVide = (): Ligne => ({ materiel: null, designation: '', quantite: '1', prix_unitaire: '', remise: '0', duree: '1' })
const ht = (l: Ligne) => Math.round(Number(l.quantite || 0) * Math.round(Number(l.prix_unitaire || 0) * (100 - Number(l.remise || 0)) / 100) * Number(l.duree || 0))
/** Date et heure pour un champ datetime-local, à l'heure du poste. */
const local = (iso: string | null) => (iso ? new Date(new Date(iso).getTime() - new Date(iso).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '')

export function ListeDevis({ peutCreer }: { peutCreer: boolean }) {
  const [liste, setListe] = useState<Devis[] | null>(null)
  const [filtre, setFiltre] = useState({ search: '', statut: '' })
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Page<Devis>>(`/commercial/devis/?${new URLSearchParams(filtre)}&page_size=100`).then((p) => setListe(p.results)).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  return (
    <>
      <div className="barre">
        <h2>Devis de location</h2>
        {peutCreer && <a className="bouton" href="#/devis/nouveau">Nouveau devis</a>}
      </div>
      <div className="grille filtres">
        <label>Recherche<input placeholder="N°, client, libellé" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>État
          <select value={filtre.statut} onChange={(e) => setFiltre({ ...filtre, statut: e.target.value })}>
            {STATUTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucun devis.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Date</th><th>Client</th><th>Libellé</th><th>Servi par</th><th className="nombre">Total HT</th><th>État</th></tr></thead>
            <tbody>
              {liste.map((d) => (
                <tr key={d.id}>
                  <td><a href={`#/devis/${d.id}`}>{d.numero}</a></td><td>{dateFr(d.date)}</td><td>{d.client_nom}</td>
                  <td>{d.libelle}<br /><span className="aide">{d.type_loyer_libelle}</span></td><td>{d.commercial_nom}</td>
                  <td className="nombre">{montant(d.totaux.total_ht)}</td>
                  <td><span className={`pastille ${pastille(d)}`}>{d.statut_libelle}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function FormulaireDevis({ id }: { id?: number }) {
  const [clients, setClients] = useState<Tiers[]>([])
  const [sites, setSites] = useState<Site[]>([])
  const [materiels, setMateriels] = useState<Materiel[]>([])
  const [d, setD] = useState<Saisie>({
    client: '', contact: '', libelle: '', activite: '', site: '', type_loyer: 'MOIS', date: aujourdhui(), validite: null, date_debut: null, date_retour: null,
    lieu: '', mode_facturation: 'ECHU', echeance: '30 JOURS NETS', mode_reglement: 'VIREMENT', exonere_tva: false, taux_tva: '18', conditions: '', lignes: [ligneVide()],
  })
  const [nouveau, setNouveau] = useState<{ code: string; raison_sociale: string; adresse: string; ville: string; telephone: string; numero_contribuable: string } | null>(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    api<Page<Tiers>>('/tiers/?est_client=true&actif=true&page_size=200').then((p) => setClients(p.results)).catch((e: Error) => setErreur(e.message))
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    api<Page<Materiel>>('/technique/materiels/?page_size=200').then((p) => setMateriels(p.results.filter((m) => m.etat !== 'REFORME'))).catch(() => undefined)
    if (id) api<Devis>(`/commercial/devis/${id}/`).then((x) => setD({ ...x, lignes: x.lignes.map((l) => ({ ...l, quantite: String(Number(l.quantite)), prix_unitaire: String(Number(l.prix_unitaire)), remise: String(Number(l.remise)), duree: String(Number(l.duree)) })) })).catch((e: Error) => setErreur(e.message))
  }, [id])

  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setD((x) => ({ ...x, [k]: v }))
  const ligne = (i: number, modif: Partial<Ligne>) => setD((x) => ({ ...x, lignes: x.lignes.map((l, j) => (j === i ? { ...l, ...modif } : l)) }))
  const totalHt = d.lignes.reduce((s, l) => s + ht(l), 0)
  const tva = d.exonere_tva ? 0 : Math.round((totalHt * Number(d.taux_tva || 0)) / 100)
  const unite = LOYERS.find(([v]) => v === d.type_loyer)?.[2] ?? ''

  async function creerClient() {
    if (!nouveau) return
    setErreur('')
    try {
      const c = await api<Tiers>('/tiers/', { method: 'POST', body: JSON.stringify({ ...nouveau, est_client: true }) })
      setClients((x) => [...x, c].sort((a, b) => a.raison_sociale.localeCompare(b.raison_sociale)))
      champ('client', c.id)
      setNouveau(null)
    } catch (err) {
      setErreur((err as Error).message)
    }
  }

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const corps = {
        ...d, validite: d.validite || null, date_debut: d.date_debut || null, date_retour: d.date_retour ? new Date(d.date_retour).toISOString() : null,
        lignes: d.lignes.map((l) => ({ materiel: l.materiel, designation: l.designation, quantite: l.quantite, prix_unitaire: l.prix_unitaire, remise: l.remise || '0', duree: l.duree || '1' })),
      }
      const x = await api<Devis>(id ? `/commercial/devis/${id}/` : '/commercial/devis/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(corps) })
      location.hash = `#/devis/${x.id}`
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <form className="fiche" onSubmit={enregistrer}>
      <p><a href={id ? `#/devis/${id}` : '#/devis'}>← {id ? 'Retour au devis' : 'Devis'}</a></p>
      <h2>{id ? 'Modifier le devis' : 'Nouveau devis de location'}</h2>
      <fieldset>
        <legend>Client</legend>
        <div className="grille">
          <label>Client
            <select required value={d.client} onChange={(e) => champ('client', Number(e.target.value))}>
              <option value="">Choisir…</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.raison_sociale} ({c.code})</option>)}
            </select>
          </label>
          <label>Interlocuteur (facultatif)<input maxLength={150} value={d.contact} onChange={(e) => champ('contact', e.target.value)} /></label>
        </div>
        {!nouveau && <button type="button" className="lien" onClick={() => setNouveau({ code: '', raison_sociale: '', adresse: '', ville: '', telephone: '', numero_contribuable: '' })}>Le client n'est pas dans la liste</button>}
        {nouveau && (
          <div className="grille">
            <label>N° client<input maxLength={20} value={nouveau.code} onChange={(e) => setNouveau({ ...nouveau, code: e.target.value })} /></label>
            <label>Raison sociale<input value={nouveau.raison_sociale} onChange={(e) => setNouveau({ ...nouveau, raison_sociale: e.target.value })} /></label>
            <label>Adresse<input value={nouveau.adresse} onChange={(e) => setNouveau({ ...nouveau, adresse: e.target.value })} /></label>
            <label>Ville<input value={nouveau.ville} onChange={(e) => setNouveau({ ...nouveau, ville: e.target.value })} /></label>
            <label>Téléphone<input value={nouveau.telephone} onChange={(e) => setNouveau({ ...nouveau, telephone: e.target.value })} /></label>
            <label>N° contribuable<input value={nouveau.numero_contribuable} onChange={(e) => setNouveau({ ...nouveau, numero_contribuable: e.target.value })} /></label>
            <div className="actions">
              <button type="button" className="secondaire" disabled={!nouveau.code || !nouveau.raison_sociale} onClick={creerClient}>Créer ce client</button>
              <button type="button" className="lien" onClick={() => setNouveau(null)}>Annuler</button>
            </div>
          </div>
        )}
      </fieldset>
      <fieldset>
        <legend>Location</legend>
        <label>Libellé<input required maxLength={200} placeholder="Mise à disposition d'un chariot élévateur 3,5 t" value={d.libelle} onChange={(e) => champ('libelle', e.target.value)} /></label>
        <div className="grille">
          <label>Agence
            <select required value={d.site} onChange={(e) => champ('site', Number(e.target.value))}>
              <option value="">Choisir…</option>
              {sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </label>
          <label>Activité
            <select value={d.activite} onChange={(e) => champ('activite', e.target.value)}>{ACTIVITES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          <label>Type de loyer
            <select value={d.type_loyer} onChange={(e) => champ('type_loyer', e.target.value)}>{LOYERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          <label>Date du devis<input type="date" required value={d.date} onChange={(e) => champ('date', e.target.value)} /></label>
          <label>Valable jusqu'au<input type="date" min={d.date} value={d.validite ?? ''} onChange={(e) => champ('validite', e.target.value)} /></label>
          <label>Début prévu<input type="date" value={d.date_debut ?? ''} onChange={(e) => champ('date_debut', e.target.value)} /></label>
          <label>Retour prévu<input type="datetime-local" value={local(d.date_retour)} onChange={(e) => champ('date_retour', e.target.value ? new Date(e.target.value).toISOString() : null)} /></label>
          <label>Lieu d'utilisation<input maxLength={200} value={d.lieu} onChange={(e) => champ('lieu', e.target.value)} /></label>
        </div>
        <p className="aide">Sans date de validité, le devis est valable 30 jours.</p>
      </fieldset>
      <fieldset>
        <legend>Lignes</legend>
        {d.lignes.map((l, i) => (
          <div className="ligne devis" key={i}>
            <label>Matériel du parc
              <select value={l.materiel ?? ''} onChange={(e) => {
                const m = materiels.find((x) => String(x.id) === e.target.value)
                ligne(i, { materiel: m ? m.id : null, designation: l.designation || (m ? m.designation : '') })
              }}>
                <option value="">Aucun</option>
                {materiels.map((m) => <option key={m.id} value={m.id}>{m.code} · {m.designation}</option>)}
              </select>
            </label>
            <label>Désignation<input required maxLength={200} value={l.designation} onChange={(e) => ligne(i, { designation: e.target.value })} /></label>
            <label>Qté<input required type="number" min="0.01" step="0.01" value={l.quantite} onChange={(e) => ligne(i, { quantite: e.target.value })} /></label>
            <label>Prix unit. HT<input required type="number" min="0" step="1" value={l.prix_unitaire} onChange={(e) => ligne(i, { prix_unitaire: e.target.value })} /></label>
            <label>Remise %<input type="number" min="0" max="100" step="0.01" value={l.remise} onChange={(e) => ligne(i, { remise: e.target.value })} /></label>
            <label>Durée<input required type="number" min="0.01" step="0.01" title={unite} value={l.duree} onChange={(e) => ligne(i, { duree: e.target.value })} /></label>
            <div className="nombre"><span className="aide">Montant HT</span><br /><strong>{montant(ht(l))}</strong></div>
            {d.lignes.length > 1 && <button type="button" className="discret" onClick={() => champ('lignes', d.lignes.filter((_, j) => j !== i))}>Retirer</button>}
          </div>
        ))}
        <p className="aide">La durée se compte en {unite === 'forfait' ? 'forfaits (laisser 1)' : unite}. Le transport ou l'opérateur se mettent sur une ligne à part, durée 1.</p>
        <button type="button" className="secondaire" onClick={() => champ('lignes', [...d.lignes, ligneVide()])}>Ajouter une ligne</button>
        <p className="nombre">Total HT <strong>{montant(totalHt)}</strong> · TVA <strong>{d.exonere_tva ? 'exonéré' : montant(tva)}</strong> · Total TTC <strong>{montant(totalHt + tva)} XOF</strong></p>
      </fieldset>
      <fieldset>
        <legend>Conditions</legend>
        <div className="grille">
          <label>Mode de facturation
            <select value={d.mode_facturation} onChange={(e) => champ('mode_facturation', e.target.value)}>{FACTURATIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          <label>Échéance de paiement<input maxLength={100} value={d.echeance} onChange={(e) => champ('echeance', e.target.value)} /></label>
          <label>Règlement
            <select value={d.mode_reglement} onChange={(e) => champ('mode_reglement', e.target.value)}>{REGLEMENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          {!d.exonere_tva && <label>TVA %<input type="number" min="0" max="100" step="0.01" value={d.taux_tva} onChange={(e) => champ('taux_tva', e.target.value)} /></label>}
        </div>
        <label className="case"><input type="checkbox" checked={d.exonere_tva} onChange={(e) => champ('exonere_tva', e.target.checked)} />Client exonéré de TVA</label>
        <label>Conditions particulières (facultatif)<textarea value={d.conditions} onChange={(e) => champ('conditions', e.target.value)} /></label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours}>{enCours ? 'Enregistrement…' : 'Enregistrer le brouillon'}</button>
        <a href={id ? `#/devis/${id}` : '#/devis'}>Annuler</a>
      </div>
    </form>
  )
}

export function DetailDevis({ id }: { id: number }) {
  const [d, setD] = useState<Devis | null>(null)
  const [s, setS] = useState({ reference_client: '', accepte_le: aujourdhui(), motif: '' })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const charger = useCallback(() => {
    api<Devis>(`/commercial/devis/${id}/`).then(setD).catch((e: Error) => setErreur(e.message))
  }, [id])
  useEffect(charger, [charger])

  async function agir(action: string, corps: object = {}) {
    setErreur('')
    setEnCours(true)
    try {
      setD(await api<Devis>(`/commercial/devis/${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
      setS((x) => ({ ...x, motif: '' }))
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  if (!d) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const t = d.totaux
  const annulable = d.statut === 'BROUILLON' || d.statut === 'ENVOYE' || (d.statut === 'ACCEPTE' && d.peut_gerer)
  return (
    <div className="fiche">
      <p><a href="#/devis">← Devis</a></p>
      <div className="barre">
        <h2>{d.statut === 'ACCEPTE' ? 'Commande client' : 'Devis'} {d.numero}</h2>
        <div className="actions">
          <button className="secondaire" onClick={() => ouvrirFichier(`/commercial/devis/${id}/pdf/`).catch((e: Error) => setErreur(e.message))}>Ouvrir le PDF</button>
          {d.peut_agir && d.statut === 'BROUILLON' && <a className="bouton secondaire" href={`#/devis/${id}/modifier`}>Modifier</a>}
        </div>
      </div>
      <p className="statut">{d.statut_libelle}</p>
      <dl>
        <dt>Client</dt><dd><strong>{d.client_nom}</strong>{d.contact && ` · ${d.contact}`}</dd>
        <dt>Libellé</dt><dd>{d.libelle}</dd>
        <dt>Date</dt><dd>{dateFr(d.date)}, valable jusqu'au {dateFr(d.validite)}</dd>
        <dt>Agence</dt><dd>{d.site_nom}{d.activite && ` · ${d.activite_libelle}`}</dd>
        <dt>Servi par</dt><dd>{d.commercial_nom}</dd>
        <dt>Loyer</dt><dd>{d.type_loyer_libelle} · {d.mode_facturation_libelle}</dd>
        {(d.date_debut || d.date_retour) && <><dt>Période</dt><dd>{[d.date_debut && `début le ${dateFr(d.date_debut)}`, d.date_retour && `retour le ${new Date(d.date_retour).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })}`].filter(Boolean).join(', ')}</dd></>}
        {d.lieu && <><dt>Lieu</dt><dd>{d.lieu}</dd></>}
        <dt>Paiement</dt><dd>{d.echeance} · {d.mode_reglement_libelle}</dd>
        {d.conditions && <><dt>Conditions</dt><dd style={{ whiteSpace: 'pre-line' }}>{d.conditions}</dd></>}
        {d.accepte_le && <><dt>Accepté</dt><dd>le {dateFr(d.accepte_le)}{d.reference_client && ` · commande du client n° ${d.reference_client}`}</dd></>}
        {d.motif && <><dt>Motif</dt><dd>{d.motif}</dd></>}
      </dl>
      <div className="defilant">
        <table>
          <thead><tr><th className="nombre">Qté</th><th>Désignation</th><th className="nombre">Prix unit. HT</th><th className="nombre">Remise</th><th className="nombre">Durée</th><th className="nombre">Montant HT</th></tr></thead>
          <tbody>
            {d.lignes.map((l, i) => (
              <tr key={i}>
                <td className="nombre">{nombre(l.quantite)}</td><td>{l.designation}{l.materiel_nom && <><br /><span className="aide">{l.materiel_nom}</span></>}</td>
                <td className="nombre">{montant(l.prix_unitaire)}</td><td className="nombre">{Number(l.remise) ? `${nombre(l.remise)} %` : ''}</td>
                <td className="nombre">{nombre(l.duree)}</td><td className="nombre">{montant(l.montant_ht ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="nombre">Total HT <strong>{montant(t.total_ht)}</strong> · TVA <strong>{d.exonere_tva ? 'exonéré' : montant(t.total_tva)}</strong> · Total TTC <strong>{montant(t.total_ttc)} XOF</strong></p>
      <p className="aide">{t.en_lettres}</p>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      {d.peut_agir && d.statut === 'BROUILLON' && (
        <fieldset>
          <legend>Envoi au client</legend>
          <p className="aide">Tant qu'il est en brouillon, le PDF porte la mention « PROJET ». Une fois envoyé, le devis est figé.</p>
          <div className="actions"><button disabled={enCours} onClick={() => agir('envoyer')}>Marquer comme envoyé au client</button></div>
        </fieldset>
      )}
      {d.peut_agir && d.statut === 'ENVOYE' && (
        <fieldset>
          <legend>Réponse du client</legend>
          <div className="grille">
            <label>N° de bon de commande du client (facultatif)<input maxLength={60} value={s.reference_client} onChange={(e) => setS({ ...s, reference_client: e.target.value })} /></label>
            <label>Accepté le<input type="date" min={d.date} max={aujourdhui()} value={s.accepte_le} onChange={(e) => setS({ ...s, accepte_le: e.target.value })} /></label>
          </div>
          <div className="actions">
            <button disabled={enCours} onClick={() => agir('accepter', s)}>Le client a accepté</button>
            <button className="secondaire" disabled={enCours} onClick={() => agir('reprendre')}>Reprendre pour le modifier</button>
          </div>
        </fieldset>
      )}
      {d.peut_agir && d.statut === 'REFUSE' && <div className="actions"><button className="secondaire" disabled={enCours} onClick={() => agir('reprendre')}>Reprendre pour une nouvelle offre</button></div>}
      {d.peut_agir && annulable && (
        <fieldset>
          <legend>{d.statut === 'ENVOYE' ? 'Refus ou annulation' : 'Annulation'}</legend>
          <label>Motif<textarea value={s.motif} onChange={(e) => setS({ ...s, motif: e.target.value })} /></label>
          <div className="actions">
            {d.statut === 'ENVOYE' && <button className="secondaire" disabled={enCours} onClick={() => agir('refuser', { motif: s.motif })}>Le client a refusé</button>}
            <button className="danger" disabled={enCours} onClick={() => agir('annuler', { motif: s.motif })}>Annuler {d.statut === 'ACCEPTE' ? 'la commande' : 'le devis'}</button>
          </div>
        </fieldset>
      )}
      <PiecesJointes modele="commercial.devis" objet={id} aide="Joignez ici le bon de commande du client ou le devis signé." />
    </div>
  )
}
