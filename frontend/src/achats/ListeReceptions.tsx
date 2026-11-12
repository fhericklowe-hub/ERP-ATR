import { useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { montant } from './commandes'
import type { Reception } from './receptions'
import { dateFr } from './types'

const FILTRES = [['', 'Tous'], ['BROUILLON', 'Brouillons'], ['VALIDE', 'Validés'], ['ANNULE', 'Annulés']]

export default function ListeReceptions() {
  const [statut, setStatut] = useState('')
  const [bons, setBons] = useState<Reception[] | null>(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    setBons(null)
    setErreur('')
    api<Page<Reception>>(`/achats/bons-reception/?statut=${statut}`)
      .then((p) => setBons(p.results))
      .catch((e: Error) => setErreur(e.message))
  }, [statut])

  return (
    <>
      <div className="barre">
        <h2>Bons de réception</h2>
        <a className="bouton" href="#/commandes?statut=TRANSMIS">Commandes à recevoir</a>
      </div>
      <p className="aide">Une réception se saisit depuis un bon de commande transmis au fournisseur.</p>
      <label className="filtre">
        Statut
        <select value={statut} onChange={(e) => setStatut(e.target.value)}>
          {FILTRES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      {erreur && <p className="erreur">{erreur}</p>}
      {!bons && !erreur && <p>Chargement…</p>}
      {bons?.length === 0 && <p>Aucun bon de réception.</p>}
      {bons && bons.length > 0 && (
        <div className="defilant">
          <table>
            <thead>
              <tr>
                <th>N°</th><th>Date</th><th>Fournisseur</th><th>N° livraison</th><th>Commande</th>
                <th>Réceptionnaire</th><th className="nombre">Valeur HT</th><th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {bons.map((b) => (
                <tr key={b.id}>
                  <td><a href={`#/receptions/${b.id}`}>{b.numero}</a></td>
                  <td>{dateFr(b.date)}</td>
                  <td>{b.fournisseur_nom}</td>
                  <td>{b.numero_livraison}</td>
                  <td><a href={`#/commandes/${b.commande}`}>{b.commande_numero}</a></td>
                  <td>{b.receptionnaire_nom}</td>
                  <td className="nombre">{montant(b.total_ht)}</td>
                  <td>{b.statut_libelle}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
