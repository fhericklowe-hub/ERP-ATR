import { useCallback, useEffect, useState } from 'react'
import { api, ouvrirFichier } from '../api'
import { montant } from './commandes'
import { type Reception, qte } from './receptions'
import { dateFr, dateHeureFr } from './types'

export default function DetailReception({ id }: { id: number }) {
  const [b, setB] = useState<Reception | null>(null)
  const [erreur, setErreur] = useState('')
  const [motif, setMotif] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    api<Reception>(`/achats/bons-reception/${id}/`).then(setB).catch((e: Error) => setErreur(e.message))
  }, [id])
  useEffect(charger, [charger])

  async function agir(action: string, corps: object = {}) {
    setEnCours(true)
    setErreur('')
    try {
      setB(await api<Reception>(`/achats/bons-reception/${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
      setMotif('')
    } catch (e) {
      setErreur((e as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const pdf = () => ouvrirFichier(`/achats/bons-reception/${id}/pdf/`).catch((e: Error) => setErreur(e.message))

  if (!b) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>

  return (
    <div className="fiche">
      <p><a href="#/receptions">← Bons de réception</a></p>
      <div className="barre">
        <h2>{b.numero}</h2>
        <button className="secondaire" onClick={pdf}>{b.statut === 'VALIDE' ? 'Imprimer le bon (PDF)' : 'Aperçu PDF'}</button>
      </div>
      <p className="statut">
        {b.statut_libelle}
        {b.statut === 'VALIDE' && b.valide_le && ` le ${dateHeureFr(b.valide_le)}`}
        {b.statut === 'ANNULE' && ` par ${b.annule_par_nom} : ${b.motif_annulation}`}
      </p>
      {b.modifiable && <p className="aide">Brouillon : les quantités ne comptent sur la commande qu'après validation.</p>}

      <dl>
        <dt>Commande</dt><dd><a href={`#/commandes/${b.commande}`}>{b.commande_numero}</a>{b.objet && ` · ${b.objet}`}</dd>
        <dt>Fournisseur</dt><dd>{b.fournisseur_nom}</dd>
        <dt>Date de réception</dt><dd>{dateFr(b.date)}</dd>
        <dt>N° de livraison</dt><dd>{b.numero_livraison || '--'}</dd>
        <dt>Imputation</dt><dd>{b.site_nom} · {b.service_nom}</dd>
        <dt>Réceptionnaire</dt><dd>{b.receptionnaire_nom}</dd>
        {b.observations && <><dt>Observations</dt><dd>{b.observations}</dd></>}
        {b.ancien_numero && <><dt>Ancien logiciel</dt><dd>{b.ancien_numero}</dd></>}
      </dl>

      <h3>Articles reçus</h3>
      <div className="defilant">
        <table>
          <thead>
            <tr>
              <th>Référence</th><th>Désignation</th><th className="nombre">Commandé</th><th className="nombre">Reçu</th>
              <th className="nombre">En stock</th><th className="nombre">Valeur HT</th>
            </tr>
          </thead>
          <tbody>
            {b.lignes.map((l) => (
              <tr key={l.id}>
                <td>{l.reference}</td>
                <td>
                  {l.designation}
                  {(l.numero_materiel || l.numero_serie || l.immatriculation) && (
                    <><br /><span className="aide">
                      {[l.numero_materiel && `N° matériel ${l.numero_materiel}`, l.numero_serie && `N° série ${l.numero_serie}`,
                        l.immatriculation && `Identité ${l.immatriculation}`].filter(Boolean).join(' · ')}
                    </span></>
                  )}
                  {l.observations && <><br /><span className="aide">{l.observations}</span></>}
                </td>
                <td className="nombre">{qte(l.quantite_commandee)}</td>
                <td className="nombre">{qte(l.quantite_recue)}</td>
                <td className="nombre">{qte(l.quantite_stock)}</td>
                <td className="nombre">{montant(l.montant_ht ?? 0, b.devise)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="nombre">Valeur HT reçue <strong>{montant(b.total_ht, b.devise)} {b.devise}</strong></p>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      {b.modifiable && b.peut_preparer && (
        <div className="actions">
          <button disabled={enCours} onClick={() => agir('valider')}>Valider la réception</button>
          <a className="bouton secondaire" href={`#/receptions/${b.id}/modifier`}>Modifier</a>
        </div>
      )}

      {b.peut_annuler && (
        <fieldset>
          <legend>Annulation</legend>
          <label>Motif de l'annulation
            <textarea value={motif} onChange={(e) => setMotif(e.target.value)} />
          </label>
          <div className="actions">
            <button className="danger" disabled={enCours} onClick={() => agir('annuler', { commentaire: motif })}>Annuler le bon de réception</button>
          </div>
        </fieldset>
      )}
    </div>
  )
}
