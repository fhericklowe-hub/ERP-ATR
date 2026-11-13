import { useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { type Demande, URGENCES, dateFr, dateHeureFr } from './types'
import BoutonExcel from '../BoutonExcel'

const FILTRES = [
  ['', 'Toutes'],
  ['BROUILLON', 'Brouillons'],
  ['ATT_SERVICE', 'Attente service'],
  ['ATT_DT', 'Attente DT'],
  ['ATT_ACHATS', 'Attente achats'],
  ['RENVOYEE', 'Renvoyées'],
  ['VALIDEE', 'Validées'],
  ['REFUSEE', 'Refusées'],
]

export default function Liste() {
  const [statut, setStatut] = useState('')
  const [demandes, setDemandes] = useState<Demande[] | null>(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    setDemandes(null)
    api<Page<Demande>>(`/achats/demandes/?statut=${statut}`)
      .then((p) => setDemandes(p.results))
      .catch((e: Error) => setErreur(e.message))
  }, [statut])

  return (
    <>
      <div className="barre">
        <h2>Demandes d'achat</h2>
        <div className="actions">
          <BoutonExcel chemin="/achats/demandes/" nom="demandes-achat" filtres={{ statut }} onErreur={setErreur} />
          <a className="bouton" href="#/demandes/nouvelle">Nouvelle demande</a>
        </div>
      </div>
      <label className="filtre">
        Statut
        <select value={statut} onChange={(e) => setStatut(e.target.value)}>
          {FILTRES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      {erreur && <p className="erreur">{erreur}</p>}
      {!demandes && !erreur && <p>Chargement…</p>}
      {demandes?.length === 0 && <p>Aucune demande.</p>}
      {demandes && demandes.length > 0 && (
        <div className="defilant">
          <table>
            <thead>
              <tr>
                <th>N°</th><th>Date</th><th>Demandeur</th><th>Service</th><th>Site</th>
                <th>Urgence</th><th>Statut</th><th>Acheteur</th><th>BC attendu avant</th>
              </tr>
            </thead>
            <tbody>
              {demandes.map((d) => (
                <tr key={d.id}>
                  <td><a href={`#/demandes/${d.id}`}>{d.numero}</a></td>
                  <td>{dateFr(d.date_demande)}</td>
                  <td>{d.demandeur_nom}</td>
                  <td>{d.service_nom}</td>
                  <td>{d.site_nom}</td>
                  <td><span className={`pastille u${d.urgence}`}>{URGENCES[d.urgence]}</span></td>
                  <td>{d.statut_libelle}{d.peut_valider && <strong> · à valider</strong>}</td>
                  <td>{d.acheteur_nom}</td>
                  <td className={d.en_retard ? 'erreur' : ''}>
                    {dateHeureFr(d.echeance_commande)}{d.en_retard && ' (en retard)'}
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
