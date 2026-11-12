import { type FormEvent, useEffect, useState } from 'react'
import { api } from '../api'
import type { Commande } from './commandes'
import { type LigneReception, type Reception, qte } from './receptions'

type Ligne = LigneReception & { reste: number; materiel: boolean }

const aujourdHui = () => new Date().toLocaleDateString('fr-CA')

/** Saisie d'une réception sur un bon de commande (commandeId) ou correction d'un brouillon (id). */
export default function FormulaireReception({ commandeId, id }: { commandeId?: number; id?: number }) {
  const [commande, setCommande] = useState<Commande | null>(null)
  const [date, setDate] = useState(aujourdHui())
  const [numeroLivraison, setNumeroLivraison] = useState('')
  const [observations, setObservations] = useState('')
  const [ancienNumero, setAncienNumero] = useState('')
  const [lignes, setLignes] = useState<Ligne[]>([])
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    (async () => {
      const br = id ? await api<Reception>(`/achats/bons-reception/${id}/`) : null
      const bc = await api<Commande>(`/achats/bons-commande/${br ? br.commande : commandeId}/`)
      setCommande(bc)
      if (br) {
        setDate(br.date)
        setNumeroLivraison(br.numero_livraison)
        setObservations(br.observations)
        setAncienNumero(br.ancien_numero)
      }
      // Une ligne par article commandé. Par défaut on propose de recevoir tout ce qui reste.
      setLignes(bc.lignes.map((lc) => {
        const reste = Number(lc.quantite) - Number(lc.quantite_recue ?? 0)
        const saisie = br?.lignes.find((l) => l.ligne_commande === lc.id)
        const recue = saisie ? String(Number(saisie.quantite_recue)) : br ? '0' : String(reste)
        return {
          ligne_commande: lc.id!, reference: lc.reference, designation: lc.designation, quantite_commandee: lc.quantite,
          quantite_recue: recue, quantite_stock: saisie ? String(Number(saisie.quantite_stock)) : recue,
          numero_materiel: saisie?.numero_materiel ?? '', numero_serie: saisie?.numero_serie ?? '',
          immatriculation: saisie?.immatriculation ?? '', observations: saisie?.observations ?? '', reste,
          materiel: Boolean(saisie?.numero_materiel || saisie?.numero_serie || saisie?.immatriculation),
        }
      }))
    })().catch((e: Error) => setErreur(e.message))
  }, [id, commandeId])

  const ligne = (i: number, modif: Partial<Ligne>) => setLignes((x) => x.map((l, j) => (j === i ? { ...l, ...modif } : l)))

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!commande) return
    const recues = lignes.filter((l) => Number(l.quantite_recue) > 0)
    if (recues.length === 0) return setErreur('Indiquez au moins une quantité reçue.')
    setEnCours(true)
    setErreur('')
    try {
      const corps = JSON.stringify({
        commande: commande.id, date, numero_livraison: numeroLivraison, observations, ancien_numero: ancienNumero,
        lignes: recues.map((l) => ({
          ligne_commande: l.ligne_commande, quantite_recue: l.quantite_recue, quantite_stock: l.quantite_stock || '0',
          numero_materiel: l.materiel ? l.numero_materiel : '', numero_serie: l.materiel ? l.numero_serie : '',
          immatriculation: l.materiel ? l.immatriculation : '', observations: l.observations,
        })),
      })
      const r = await api<Reception>(id ? `/achats/bons-reception/${id}/` : '/achats/bons-reception/', { method: id ? 'PUT' : 'POST', body: corps })
      location.hash = `#/receptions/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
      setEnCours(false)
    }
  }

  if (!commande) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>

  return (
    <form className="fiche" onSubmit={enregistrer}>
      <h2>{id ? 'Modifier le bon de réception' : 'Nouveau bon de réception'}</h2>
      <p>
        Commande <a href={`#/commandes/${commande.id}`}>{commande.numero}</a> · {commande.fournisseur_nom}
        {commande.objet && ` · ${commande.objet}`}
      </p>

      <fieldset>
        <legend>Livraison</legend>
        <div className="grille">
          <label>Date de réception
            <input required type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <label>N° de livraison fournisseur
            <input value={numeroLivraison} onChange={(e) => setNumeroLivraison(e.target.value)} />
          </label>
          <label>N° dans l'ancien logiciel (facultatif)
            <input value={ancienNumero} onChange={(e) => setAncienNumero(e.target.value)} />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Quantités reçues</legend>
        <p className="aide">Laissez 0 pour un article non livré. La quantité à mettre en stock ne dépasse pas la quantité reçue.</p>
        {lignes.map((l, i) => (
          <div className="ligne reception" key={l.ligne_commande}>
            <div>
              <strong>{l.designation}</strong>{l.reference && <span className="aide"> · {l.reference}</span>}
              <br /><span className="aide">Commandé {qte(l.quantite_commandee)} · reste à recevoir {qte(l.reste)}</span>
            </div>
            <label>Reçu
              <input type="number" min="0" max={l.reste} step="0.01" disabled={l.reste <= 0} value={l.quantite_recue}
                onChange={(e) => ligne(i, { quantite_recue: e.target.value, quantite_stock: e.target.value })} />
            </label>
            <label>À mettre en stock
              <input type="number" min="0" max={l.quantite_recue || 0} step="0.01" disabled={l.reste <= 0} value={l.quantite_stock}
                onChange={(e) => ligne(i, { quantite_stock: e.target.value })} />
            </label>
            <label>Observations
              <input value={l.observations} disabled={l.reste <= 0} placeholder="Conforme, réserves…"
                onChange={(e) => ligne(i, { observations: e.target.value })} />
            </label>
            <label className="case materiel">
              <input type="checkbox" checked={l.materiel} disabled={l.reste <= 0} onChange={(e) => ligne(i, { materiel: e.target.checked })} />
              C'est un matériel (engin, véhicule)
            </label>
            {l.materiel && (
              <div className="grille materiel">
                <label>N° matériel
                  <input value={l.numero_materiel} onChange={(e) => ligne(i, { numero_materiel: e.target.value })} />
                </label>
                <label>N° de série
                  <input value={l.numero_serie} onChange={(e) => ligne(i, { numero_serie: e.target.value })} />
                </label>
                <label>Immatriculation / identité
                  <input value={l.immatriculation} onChange={(e) => ligne(i, { immatriculation: e.target.value })} />
                </label>
              </div>
            )}
          </div>
        ))}
      </fieldset>

      <label>Observations générales
        <textarea value={observations} onChange={(e) => setObservations(e.target.value)} />
      </label>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours}>{enCours ? 'Enregistrement…' : 'Enregistrer le brouillon'}</button>
        <a href={id ? `#/receptions/${id}` : `#/commandes/${commande.id}`}>Annuler</a>
      </div>
    </form>
  )
}
