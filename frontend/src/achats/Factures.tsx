import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, apiTout, type Page } from '../api'
import BoutonExcel from '../BoutonExcel'
import { montant } from './commandes'
import { dateFr } from './types'

type Rapprochement = {
  commande_ht: string; recu_ht: string; autres_factures_ht: string; facture_ht: string; cumul_facture_ht: string
  ecart_ht: string; conforme: boolean; sens: string
}
type Facture = {
  id: number; numero: string; numero_facture: string; statut: string; statut_libelle: string; commande: number; commande_numero: string
  commande_objet: string; fournisseur_nom: string; devise: string; date_facture: string; date_echeance: string | null
  montant_ht: string; montant_ttc: string; observations: string; commentaire_ecart: string; bon_a_payer_par_nom: string
  bon_a_payer_le: string | null; payee_le: string | null; reference_paiement: string; motif_annulation: string
  rapprochement: Rapprochement; modifiable: boolean; peut_bon_a_payer: boolean; peut_payer: boolean; peut_annuler: boolean; en_retard: boolean
}
type CommandeCourte = { id: number; numero: string; fournisseur_nom: string; objet: string; devise: string }

const FILTRES = [['', 'Toutes'], ['A_VERIFIER', 'À vérifier'], ['BON_A_PAYER', 'Bon à payer'], ['PAYEE', 'Payées'], ['ANNULEE', 'Annulées']]
const aujourdhui = () => new Date().toISOString().slice(0, 10)

export function ListeFactures() {
  const [statut, setStatut] = useState('')
  const [liste, setListe] = useState<Facture[] | null>(null)
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    setListe(null)
    apiTout<Facture>(`/achats/factures/?statut=${statut}`).then((p) => setListe(p)).catch((e: Error) => setErreur(e.message))
  }, [statut])
  return (
    <>
      <div className="barre">
        <h2>Factures fournisseurs</h2>
        <div className="actions">
          <BoutonExcel chemin="/achats/factures/" nom="factures-fournisseurs" filtres={{ statut }} onErreur={setErreur} />
          <a className="bouton" href="#/factures/nouvelle">Enregistrer une facture</a>
        </div>
      </div>
      <p className="aide">Une facture se contrôle par rapport au bon de commande et aux réceptions validées. Le paiement se fait dans IE : ici on donne le bon à payer puis on note le paiement.</p>
      <label className="filtre">Statut
        <select value={statut} onChange={(e) => setStatut(e.target.value)}>{FILTRES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
      </label>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p>Aucune facture.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Facture</th><th>Fournisseur</th><th>Commande</th><th>Échéance</th><th className="nombre">Montant TTC</th><th>Contrôle</th><th>Statut</th></tr></thead>
            <tbody>
              {liste.map((f) => (
                <tr key={f.id}>
                  <td><a href={`#/factures/${f.id}`}>{f.numero}</a></td>
                  <td>{f.numero_facture}<br /><span className="aide">{dateFr(f.date_facture)}</span></td>
                  <td>{f.fournisseur_nom}</td>
                  <td><a href={`#/commandes/${f.commande}`}>{f.commande_numero}</a></td>
                  <td>{f.date_echeance ? dateFr(f.date_echeance) : ''}{f.en_retard && <strong className="erreur"> · en retard</strong>}</td>
                  <td className="nombre">{montant(f.montant_ttc, f.devise)}{f.devise !== 'XOF' && ` ${f.devise}`}</td>
                  <td>{f.statut === 'ANNULEE' ? '' : f.rapprochement.conforme ? <span className="pastille complete">Conforme</span> : <span className="pastille partielle">Écart</span>}</td>
                  <td>{f.statut_libelle}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

type Saisie = { commande: number | ''; numero_facture: string; date_facture: string; date_echeance: string; montant_ht: string; montant_ttc: string; observations: string }

export default function FicheFacture({ id, commandeId }: { id?: number; commandeId?: number }) {
  const [f, setF] = useState<Facture | null>(null)
  const [saisie, setSaisie] = useState<Saisie>({ commande: commandeId ?? '', numero_facture: '', date_facture: aujourdhui(), date_echeance: '', montant_ht: '', montant_ttc: '', observations: '' })
  const [commandes, setCommandes] = useState<CommandeCourte[]>([])
  const [texte, setTexte] = useState('')
  const [datePaiement, setDatePaiement] = useState(aujourdhui())
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    if (!id) return
    api<Facture>(`/achats/factures/${id}/`).then((x) => {
      setF(x)
      setSaisie({ commande: x.commande, numero_facture: x.numero_facture, date_facture: x.date_facture, date_echeance: x.date_echeance ?? '', montant_ht: x.montant_ht, montant_ttc: x.montant_ttc, observations: x.observations })
    }).catch((e: Error) => setErreur(e.message))
  }, [id])
  useEffect(charger, [charger])
  useEffect(() => {
    if (id) return
    Promise.all(['TRANSMIS', 'CLOTURE'].map((s) => api<Page<CommandeCourte>>(`/achats/bons-commande/?statut=${s}&page_size=200`)))
      .then(([a, b]) => setCommandes([...a.results, ...b.results])).catch((e: Error) => setErreur(e.message))
  }, [id])

  const change = (k: keyof Saisie, v: string) => setSaisie((s) => {
    const suite = { ...s, [k]: v }
    if (k === 'montant_ht' && (s.montant_ttc === '' || Number(s.montant_ttc) === Math.round(Number(s.montant_ht) * 118) / 100)) suite.montant_ttc = v ? String(Math.round(Number(v) * 118) / 100) : ''
    return suite
  })

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const corps = { ...saisie, date_echeance: saisie.date_echeance || null }
      const r = await api<Facture>(id ? `/achats/factures/${id}/` : '/achats/factures/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(corps) })
      if (id) setF(r)
      else location.hash = `#/factures/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  async function agir(nom: string, corps: object = {}) {
    setErreur('')
    setEnCours(true)
    try {
      setF(await api<Facture>(`/achats/factures/${id}/${nom}/`, { method: 'POST', body: JSON.stringify(corps) }))
      setTexte('')
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const devise = f?.devise ?? commandes.find((c) => c.id === saisie.commande)?.devise ?? 'XOF'
  const r = f?.rapprochement
  const modifiable = !id || f?.modifiable
  return (
    <div className="fiche">
      <div className="barre"><h2>{f ? `Facture ${f.numero}` : 'Nouvelle facture fournisseur'}</h2><a className="bouton secondaire" href="#/factures">Retour à la liste</a></div>
      {f && <p><strong>{f.statut_libelle}</strong> · {f.fournisseur_nom} · <a href={`#/commandes/${f.commande}`}>{f.commande_numero}</a>{f.commande_objet && ` (${f.commande_objet})`}
        {f.statut === 'BON_A_PAYER' && ` · bon à payer donné par ${f.bon_a_payer_par_nom}`}
        {f.statut === 'PAYEE' && ` · payée le ${dateFr(f.payee_le!)}${f.reference_paiement ? ` (${f.reference_paiement})` : ''}`}
        {f.statut === 'ANNULEE' && ` · ${f.motif_annulation}`}</p>}
      <form className="fiche" onSubmit={enregistrer}>
        <fieldset disabled={!modifiable}>
          <legend>Facture reçue du fournisseur</legend>
          <div className="grille">
            {!id && (
              <label>Bon de commande
                <select required value={saisie.commande} onChange={(e) => change('commande', e.target.value)}>
                  <option value="">Choisir…</option>
                  {commandes.map((c) => <option key={c.id} value={c.id}>{c.numero} · {c.fournisseur_nom}{c.objet ? ` · ${c.objet}` : ''}</option>)}
                </select>
              </label>
            )}
            <label>N° de la facture<input required maxLength={50} value={saisie.numero_facture} onChange={(e) => change('numero_facture', e.target.value)} /></label>
            <label>Date de la facture<input required type="date" value={saisie.date_facture} onChange={(e) => change('date_facture', e.target.value)} /></label>
            <label>Échéance de paiement<input type="date" value={saisie.date_echeance} onChange={(e) => change('date_echeance', e.target.value)} /></label>
            <label>Montant HT ({devise})<input required type="number" min="0" step="0.01" value={saisie.montant_ht} onChange={(e) => change('montant_ht', e.target.value)} /></label>
            <label>Montant TTC ({devise})<input required type="number" min="0" step="0.01" value={saisie.montant_ttc} onChange={(e) => change('montant_ttc', e.target.value)} /></label>
          </div>
          <label>Observations<textarea value={saisie.observations} onChange={(e) => change('observations', e.target.value)} /></label>
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        {modifiable && <div className="actions"><button disabled={enCours}>{id ? 'Enregistrer' : 'Enregistrer la facture'}</button></div>}
      </form>
      {r && (
        <section aria-label="Rapprochement">
          <h3>Contrôle avec le bon de commande et les réceptions</h3>
          <div className="defilant">
            <table>
              <tbody>
                <tr><td>Montant HT du bon de commande</td><td className="nombre">{montant(r.commande_ht, devise)}</td></tr>
                <tr><td>Valeur des réceptions validées</td><td className="nombre">{montant(r.recu_ht, devise)}</td></tr>
                <tr><td>Autres factures sur cette commande</td><td className="nombre">{montant(r.autres_factures_ht, devise)}</td></tr>
                <tr><td>Cette facture</td><td className="nombre">{montant(r.facture_ht, devise)}</td></tr>
                <tr><td><strong>Écart (total facturé − reçu)</strong></td><td className="nombre"><strong>{montant(r.ecart_ht, devise)}</strong></td></tr>
              </tbody>
            </table>
          </div>
          <p className={r.conforme ? 'aide' : 'erreur'}>
            {r.conforme ? 'La facture correspond à ce qui a été reçu.' : r.sens === 'facture_superieure'
              ? 'Le total facturé dépasse ce qui a été reçu : vérifiez les quantités reçues, le prix ou des frais non prévus.'
              : 'Le total facturé est inférieur à ce qui a été reçu : une autre facture est peut-être attendue.'}
          </p>
          {f?.commentaire_ecart && <p>Justification de l'écart : {f.commentaire_ecart}</p>}
        </section>
      )}
      {f && (f.peut_bon_a_payer || f.peut_payer || f.peut_annuler) && (
        <section aria-label="Suite">
          {f.peut_payer && <label>Date du paiement<input type="date" value={datePaiement} onChange={(e) => setDatePaiement(e.target.value)} /></label>}
          <label>{f.peut_payer ? 'Référence du paiement (virement, chèque…)' : 'Justification de l\'écart ou motif de l\'annulation'}
            <input value={texte} onChange={(e) => setTexte(e.target.value)} />
          </label>
          <div className="actions">
            {f.peut_bon_a_payer && <button disabled={enCours} onClick={() => agir('bon_a_payer', { commentaire: texte })}>Donner le bon à payer</button>}
            {f.peut_payer && <button disabled={enCours} onClick={() => agir('payer', { date: datePaiement, reference: texte })}>Marquer comme payée</button>}
            {f.peut_annuler && <button className="danger" disabled={enCours} onClick={() => agir('annuler', { commentaire: texte })}>Annuler la facture</button>}
          </div>
        </section>
      )}
    </div>
  )
}
