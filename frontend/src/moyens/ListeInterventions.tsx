import { useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { dateFr } from '../achats/types'
import { type Intervention, STATUTS } from './types'

export default function ListeInterventions() {
  const [statut, setStatut] = useState('')
  const [demandes, setDemandes] = useState<Intervention[] | null>(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    setDemandes(null)
    setErreur('')
    api<Page<Intervention>>(`/moyens/interventions/?statut=${statut}&ordering=priorite,-cree_le`)
      .then((p) => setDemandes(p.results))
      .catch((e: Error) => setErreur(e.message))
  }, [statut])

  return (
    <>
      <div className="barre">
        <h2>Demandes d'intervention</h2>
        <a className="bouton" href="#/interventions/nouvelle">Nouvelle demande</a>
      </div>
      <p className="aide">Panne, réparation, entretien des locaux, du mobilier, de l'informatique ou d'un véhicule de service.</p>
      <label className="filtre">
        Statut
        <select value={statut} onChange={(e) => setStatut(e.target.value)}>
          {STATUTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      {erreur && <p className="erreur">{erreur}</p>}
      {!demandes && !erreur && <p>Chargement…</p>}
      {demandes?.length === 0 && <p>Aucune demande.</p>}
      {demandes && demandes.length > 0 && (
        <div className="defilant">
          <table>
            <thead>
              <tr><th>N°</th><th>Date</th><th>Objet</th><th>Lieu</th><th>Demandeur</th><th>Intervenant</th><th>Statut</th></tr>
            </thead>
            <tbody>
              {demandes.map((d) => (
                <tr key={d.id}>
                  <td><a href={`#/interventions/${d.id}`}>{d.numero}</a>{d.priorite === 1 && <> <span className="pastille u1">Urgente</span></>}</td>
                  <td>{dateFr(d.cree_le)}</td>
                  <td>{d.objet}<br /><span className="aide">{d.categorie_libelle}</span></td>
                  <td>{d.site_nom}{d.lieu && ` · ${d.lieu}`}</td>
                  <td>{d.demandeur_nom}</td>
                  <td>{[d.intervenant_nom, d.prestataire_nom].filter(Boolean).join(', ')}{d.date_prevue && <><br /><span className="aide">prévue le {dateFr(d.date_prevue)}</span></>}</td>
                  <td>{d.statut_libelle}{d.statut === 'NOUVELLE' && d.peut_traiter && <strong> · à traiter</strong>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
