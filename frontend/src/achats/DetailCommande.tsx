import { useCallback, useEffect, useState } from 'react'
import { api, ouvrirFichier } from '../api'
import { type Commande, montant } from './commandes'
import { dateFr, dateHeureFr } from './types'

export default function DetailCommande({ id }: { id: number }) {
  const [b, setB] = useState<Commande | null>(null)
  const [erreur, setErreur] = useState('')
  const [texte, setTexte] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    api<Commande>(`/achats/bons-commande/${id}/`).then(setB).catch((e: Error) => setErreur(e.message))
  }, [id])
  useEffect(charger, [charger])

  async function agir(action: string, corps: object = {}) {
    setEnCours(true)
    setErreur('')
    try {
      setB(await api<Commande>(`/achats/bons-commande/${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
      setTexte('')
    } catch (e) {
      setErreur((e as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const pdf = () => ouvrirFichier(`/achats/bons-commande/${id}/pdf/`).catch((e: Error) => setErreur(e.message))

  if (!b) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const t = b.totaux
  const recu = b.etat_reception !== ''

  return (
    <div className="fiche">
      <p><a href="#/commandes">← Bons de commande</a></p>
      <div className="barre">
        <h2>{b.numero}</h2>
        <button className="secondaire" onClick={pdf}>{b.definitif ? 'Imprimer le bon (PDF)' : 'Aperçu PDF (projet)'}</button>
      </div>
      <p className="statut">
        {b.statut_libelle}{b.statut === 'TRANSMIS' && b.transmis_le && ` le ${dateFr(b.transmis_le)}`}
        {b.etat_reception && <> <span className={`pastille ${b.etat_reception.toLowerCase()}`}>{b.etat_reception_libelle}</span></>}
      </p>
      {b.statut === 'VALIDE' && (
        <p>Le bon a ses deux validations : imprimez-le, faites-le signer par le responsable achats, puis transmettez-le au fournisseur.</p>
      )}

      <dl>
        <dt>Fournisseur</dt><dd>{b.fournisseur_nom}{b.reference_fournisseur && ` · devis ${b.reference_fournisseur}`}</dd>
        <dt>Demande d'achat</dt><dd><a href={`#/demandes/${b.demande}`}>{b.demande_numero}</a></dd>
        <dt>Date</dt><dd>{dateFr(b.date)}{b.date_livraison && ` · livraison pour le ${dateFr(b.date_livraison)}`}</dd>
        {b.objet && <><dt>Objet</dt><dd>{b.objet}</dd></>}
        <dt>Imputation</dt><dd>{b.site_nom} · {b.service_nom}</dd>
        <dt>Acheteur</dt><dd>{b.acheteur_nom}</dd>
        <dt>Règlement</dt><dd>{b.echeance} · {b.mode_reglement_libelle}</dd>
        {b.ancien_numero && <><dt>Ancien logiciel</dt><dd>{b.ancien_numero}</dd></>}
      </dl>

      <h3>Lignes</h3>
      <div className="defilant">
        <table>
          <thead>
            <tr>
              <th>Référence</th><th>Désignation</th><th className="nombre">Qté</th>{recu && <th className="nombre">Reçu</th>}<th className="nombre">Prix unit. HT</th>
              <th className="nombre">Remise</th><th className="nombre">TVA</th><th className="nombre">Montant HT</th>
            </tr>
          </thead>
          <tbody>
            {b.lignes.map((l) => (
              <tr key={l.id}>
                <td>{l.reference}</td><td>{l.designation}</td>
                <td className="nombre">{Number(l.quantite)}</td>
                {recu && <td className="nombre">{Number(l.quantite_recue ?? 0)}</td>}
                <td className="nombre">{montant(l.prix_unitaire, b.devise)}</td>
                <td className="nombre">{Number(l.remise) ? `${Number(l.remise)} %` : ''}</td>
                <td className="nombre">{Number(l.taux_tva)} %</td>
                <td className="nombre">{montant(l.montant_ht ?? 0, b.devise)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="nombre">
        Total HT <strong>{montant(t.total_ht, b.devise)}</strong> · TVA <strong>{montant(t.total_tva, b.devise)}</strong> · Total TTC <strong>{montant(t.total_ttc, b.devise)} {b.devise}</strong>
        {b.devise !== 'XOF' && t.contre_valeur_xof && <><br />Contre-valeur {montant(t.contre_valeur_xof)} XOF (1 {b.devise} = {Number(b.taux_change)} XOF)</>}
        <br /><span className="aide">{t.en_lettres}</span>
      </p>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      {b.modifiable && b.peut_preparer && (
        <div className="actions">
          <button disabled={enCours} onClick={() => agir('soumettre')}>Soumettre pour validation</button>
          <a className="bouton secondaire" href={`#/commandes/${b.id}/modifier`}>Modifier</a>
        </div>
      )}
      {recu && (
        <>
          <h3>Réceptions</h3>
          {b.receptions.length === 0 && <p className="aide">Aucune réception enregistrée.</p>}
          <ul>
            {b.receptions.map((r) => (
              <li key={r.id}>
                <a href={`#/receptions/${r.id}`}>{r.numero}</a> du {dateFr(r.date)}
                {r.numero_livraison && ` · livraison ${r.numero_livraison}`} · {r.statut_libelle}
              </li>
            ))}
          </ul>
          <div className="actions">
            {b.statut === 'TRANSMIS' && b.etat_reception !== 'COMPLETE' && (
              <a className="bouton" href={`#/commandes/${b.id}/recevoir`}>Saisir une réception</a>
            )}
            {b.statut === 'TRANSMIS' && b.peut_preparer && (
              <button className="secondaire" disabled={enCours} onClick={() => agir('cloturer', { commentaire: texte })}>Clôturer la commande</button>
            )}
            {b.statut === 'CLOTURE' && b.peut_preparer && (
              <button className="secondaire" disabled={enCours} onClick={() => agir('decloturer', { commentaire: texte })}>Rouvrir la commande</button>
            )}
          </div>
          {b.statut === 'TRANSMIS' && b.peut_preparer && b.etat_reception !== 'COMPLETE' && (
            <label>Motif de la clôture (obligatoire si tout n'est pas reçu)
              <input value={texte} onChange={(e) => setTexte(e.target.value)} />
            </label>
          )}
        </>
      )}

      {b.statut === 'VALIDE' && b.peut_preparer && (
        <div className="actions">
          <button disabled={enCours} onClick={() => agir('transmettre')}>Marquer comme transmis au fournisseur</button>
        </div>
      )}

      {(b.peut_valider || b.peut_annuler) && (
        <fieldset>
          <legend>{b.peut_valider ? 'Votre décision' : 'Annulation'}</legend>
          <label>{b.peut_valider ? 'Commentaire ou motif' : "Motif de l'annulation"}
            <textarea value={texte} onChange={(e) => setTexte(e.target.value)} />
          </label>
          <div className="actions">
            {b.peut_valider && <button disabled={enCours} onClick={() => agir('valider', { commentaire: texte })}>Valider</button>}
            {b.peut_valider && (
              <button className="secondaire" disabled={enCours} onClick={() => agir('refuser', { commentaire: texte })}>
                Refuser et renvoyer à l'acheteur
              </button>
            )}
            {b.peut_annuler && (
              <button className="danger" disabled={enCours} onClick={() => agir('annuler', { commentaire: texte })}>Annuler le bon</button>
            )}
          </div>
        </fieldset>
      )}

      <h3>Historique</h3>
      {b.evenements.length === 0 && <p className="aide">Brouillon, pas encore soumis.</p>}
      <ul>
        {b.evenements.map((e) => (
          <li key={e.id}>
            {dateHeureFr(e.date)} · <strong>{e.action_libelle}</strong> par {e.auteur_nom}
            {e.commentaire && ` : ${e.commentaire}`}
          </li>
        ))}
      </ul>
    </div>
  )
}
