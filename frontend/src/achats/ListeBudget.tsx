import { useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { type DemandeBudget, STATUTS, TYPES } from './budget'
import { montant } from './commandes'
import { dateFr } from './types'

export default function ListeBudget() {
  const [statut, setStatut] = useState('')
  const [type, setType] = useState('')
  const [demandes, setDemandes] = useState<DemandeBudget[] | null>(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    setDemandes(null)
    setErreur('')
    api<Page<DemandeBudget>>(`/achats/demandes-budget/?statut=${statut}&type=${type}`)
      .then((p) => setDemandes(p.results))
      .catch((e: Error) => setErreur(e.message))
  }, [statut, type])

  return (
    <>
      <div className="barre">
        <h2>Demandes liées au budget</h2>
        <a className="bouton" href="#/budget/nouvelle">Nouvelle demande</a>
      </div>
      <p className="aide">Frais généraux, sous-traitance et investissements. Les pièces techniques passent par les demandes d'achat.</p>
      <div className="grille filtres">
        <label>Type
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">Tous</option>
            {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label>Statut
          <select value={statut} onChange={(e) => setStatut(e.target.value)}>
            {STATUTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!demandes && !erreur && <p>Chargement…</p>}
      {demandes?.length === 0 && <p>Aucune demande.</p>}
      {demandes && demandes.length > 0 && (
        <div className="defilant">
          <table>
            <thead>
              <tr><th>N°</th><th>Date</th><th>Intitulé</th><th>Service</th><th>Demandeur</th><th className="nombre">Montant</th><th>Statut</th></tr>
            </thead>
            <tbody>
              {demandes.map((d) => (
                <tr key={d.id}>
                  <td><a href={`#/budget/${d.id}`}>{d.numero}</a>{d.fast_track && <> <span className="pastille u1">Fast-Track</span></>}</td>
                  <td>{dateFr(d.date)}</td>
                  <td>{d.intitule}{!d.prevu_budget && <> <span className="pastille partielle">Hors budget</span></>}</td>
                  <td>{d.service_nom}</td>
                  <td>{d.demandeur_nom}</td>
                  <td className="nombre">{d.montant ? montant(d.montant) : ''}</td>
                  <td>
                    {d.statut_libelle}
                    {(d.peut_valider || d.peut_consulter || d.peut_imputer) && <strong> · à traiter</strong>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
