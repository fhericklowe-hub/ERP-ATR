import { useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { type Commande, montant } from './commandes'
import { dateFr } from './types'

const FILTRES = [
  ['', 'Tous'],
  ['BROUILLON', 'Brouillons'],
  ['ATT_RESP', 'Attente responsable achats'],
  ['ATT_CDG', 'Attente contrôleur de gestion'],
  ['VALIDE', 'Validés, à transmettre'],
  ['TRANSMIS', 'Transmis, à recevoir'],
  ['CLOTURE', 'Clôturés'],
  ['ANNULE', 'Annulés'],
]

export default function ListeCommandes() {
  const [statut, setStatut] = useState(() => new URLSearchParams(location.hash.split('?')[1]).get('statut') ?? '')
  const [bons, setBons] = useState<Commande[] | null>(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    setBons(null)
    setErreur('')
    api<Page<Commande>>(`/achats/bons-commande/?statut=${statut}`)
      .then((p) => setBons(p.results))
      .catch((e: Error) => setErreur(e.message))
  }, [statut])

  return (
    <>
      <div className="barre">
        <h2>Bons de commande</h2>
      </div>
      <p className="aide">Un bon de commande se crée depuis une demande d'achat validée.</p>
      <label className="filtre">
        Statut
        <select value={statut} onChange={(e) => setStatut(e.target.value)}>
          {FILTRES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      {erreur && <p className="erreur">{erreur}</p>}
      {!bons && !erreur && <p>Chargement…</p>}
      {bons?.length === 0 && <p>Aucun bon de commande.</p>}
      {bons && bons.length > 0 && (
        <div className="defilant">
          <table>
            <thead>
              <tr>
                <th>N°</th><th>Date</th><th>Fournisseur</th><th>Objet</th><th>Demande</th>
                <th>Acheteur</th><th className="nombre">Total TTC</th><th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {bons.map((b) => (
                <tr key={b.id}>
                  <td><a href={`#/commandes/${b.id}`}>{b.numero}</a></td>
                  <td>{dateFr(b.date)}</td>
                  <td>{b.fournisseur_nom}</td>
                  <td>{b.objet}</td>
                  <td><a href={`#/demandes/${b.demande}`}>{b.demande_numero}</a></td>
                  <td>{b.acheteur_nom}</td>
                  <td className="nombre">{montant(b.totaux.total_ttc, b.devise)}{b.devise !== 'XOF' && ` ${b.devise}`}</td>
                  <td>
                    {b.statut_libelle}{b.peut_valider && <strong> · à valider</strong>}
                    {b.etat_reception && <><br /><span className={`pastille ${b.etat_reception.toLowerCase()}`}>{b.etat_reception_libelle}</span></>}
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
