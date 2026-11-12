import { useCallback, useEffect, useState } from 'react'
import { api, ouvrirFichier, type Page, type Service, type Tiers } from '../api'
import type { Compte, DemandeBudget, Devis, LigneBudgetaire } from './budget'
import { montant } from './commandes'
import { dateFr, dateHeureFr } from './types'

const URL = '/achats/demandes-budget'

/** Consultation des fournisseurs : saisie des devis par les achats. */
function Consultation({ d, onChange }: { d: DemandeBudget; onChange: (d: DemandeBudget) => void }) {
  const [fournisseurs, setFournisseurs] = useState<Tiers[]>([])
  const [devis, setDevis] = useState<Devis[]>(d.devis.length ? d.devis : [{ fournisseur: '', numero: '', date: null, montant: '', retenu: false }])
  const [criteres, setCriteres] = useState({
    critere_qualite: d.critere_qualite, critere_delai: d.critere_delai, critere_prix: d.critere_prix,
    critere_autre: d.critere_autre, justification_devis: d.justification_devis,
  })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    api<Page<Tiers>>('/tiers/?est_fournisseur=true&actif=true').then((p) => setFournisseurs(p.results)).catch((e: Error) => setErreur(e.message))
  }, [])

  const ligne = (i: number, modif: Partial<Devis>) => setDevis((x) => x.map((l, j) => (j === i ? { ...l, ...modif } : l)))
  const retenir = (i: number) => setDevis((x) => x.map((l, j) => ({ ...l, retenu: j === i })))

  async function envoyer(proposer: boolean) {
    setEnCours(true)
    setErreur('')
    try {
      const complets = devis.filter((x) => x.fournisseur && x.montant)
      let r = await api<DemandeBudget>(`${URL}/${d.id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ ...criteres, devis: complets.map(({ fournisseur, numero, date, montant: m, retenu }) => ({ fournisseur, numero, date: date || null, montant: m, retenu })) }),
      })
      if (proposer) r = await api<DemandeBudget>(`${URL}/${d.id}/proposer/`, { method: 'POST', body: '{}' })
      onChange(r)
    } catch (e) {
      setErreur((e as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <fieldset>
      <legend>Consultation des fournisseurs</legend>
      <p className="aide">
        {d.est_investissement ? 'Enregistrez le devis retenu.' : 'Trois devis sont attendus. Cochez celui qui est retenu.'}
      </p>
      {devis.map((x, i) => (
        <div className="ligne devis" key={i}>
          <label>Fournisseur
            <select value={x.fournisseur} onChange={(e) => ligne(i, { fournisseur: Number(e.target.value) })}>
              <option value="">Choisir…</option>
              {fournisseurs.map((f) => <option key={f.id} value={f.id}>{f.raison_sociale}</option>)}
            </select>
          </label>
          <label>N° de devis
            <input value={x.numero} onChange={(e) => ligne(i, { numero: e.target.value })} />
          </label>
          <label>Date
            <input type="date" value={x.date ?? ''} onChange={(e) => ligne(i, { date: e.target.value })} />
          </label>
          <label>Montant (XOF)
            <input type="number" min="1" step="1" value={x.montant} onChange={(e) => ligne(i, { montant: e.target.value })} />
          </label>
          <label className="case">
            <input type="radio" name="retenu" checked={x.retenu} onChange={() => retenir(i)} /> Retenu
          </label>
          {devis.length > 1 && <button type="button" className="discret" onClick={() => setDevis(devis.filter((_, j) => j !== i))}>Retirer</button>}
        </div>
      ))}
      <button type="button" className="secondaire" onClick={() => setDevis([...devis, { fournisseur: '', numero: '', date: null, montant: '', retenu: false }])}>
        Ajouter un devis
      </button>
      <div className="actions">
        <span>Critères de sélection :</span>
        {([['critere_qualite', 'Qualité'], ['critere_delai', 'Délai'], ['critere_prix', 'Prix']] as const).map(([k, l]) => (
          <label className="case" key={k}>
            <input type="checkbox" checked={criteres[k]} onChange={(e) => setCriteres({ ...criteres, [k]: e.target.checked })} /> {l}
          </label>
        ))}
      </div>
      <div className="grille">
        <label>Autres critères
          <input value={criteres.critere_autre} onChange={(e) => setCriteres({ ...criteres, critere_autre: e.target.value })} />
        </label>
        {!d.est_investissement && (
          <label>Justification s'il y a moins de trois devis
            <input value={criteres.justification_devis} onChange={(e) => setCriteres({ ...criteres, justification_devis: e.target.value })} />
          </label>
        )}
      </div>
      {fournisseurs.length === 0 && <p className="aide">Aucun fournisseur enregistré. Ils se créent dans l'administration, rubrique Tiers.</p>}
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours} onClick={() => envoyer(true)}>Proposer le fournisseur retenu</button>
        <button className="secondaire" disabled={enCours} onClick={() => envoyer(false)}>Enregistrer sans proposer</button>
      </div>
    </fieldset>
  )
}

/** Imputation par le contrôle de gestion. */
function Imputation({ d, onChange }: { d: DemandeBudget; onChange: (d: DemandeBudget) => void }) {
  const [services, setServices] = useState<Service[]>([])
  const [comptes, setComptes] = useState<Compte[]>([])
  const [lignes, setLignes] = useState<LigneBudgetaire[]>([])
  const [s, setS] = useState({
    service_impute: d.service_impute ?? (d.service as number), compte: d.compte, ligne_budgetaire: d.ligne_budgetaire,
    prevu_budget: d.prevu_budget, motif_hors_budget: d.motif_hors_budget, duree_amortissement: d.duree_amortissement,
  })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    Promise.all([
      api<Page<Service>>('/services/?actif=true'), api<Compte[]>('/comptes-charge/?actif=true'),
      api<LigneBudgetaire[]>('/achats/lignes-budgetaires/?actif=true'),
    ]).then(([se, co, li]) => { setServices(se.results); setComptes(co); setLignes(li) }).catch((e: Error) => setErreur(e.message))
  }, [])

  async function enregistrer() {
    setEnCours(true)
    setErreur('')
    try {
      onChange(await api<DemandeBudget>(`${URL}/${d.id}/`, {
        method: 'PATCH', body: JSON.stringify({ ...s, ligne_budgetaire: s.prevu_budget ? s.ligne_budgetaire : null }),
      }))
    } catch (e) {
      setErreur((e as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const compte = comptes.find((c) => c.id === s.compte)
  return (
    <fieldset>
      <legend>Imputation (contrôle de gestion)</legend>
      <div className="grille">
        <label>Service imputé
          <select value={s.service_impute ?? ''} onChange={(e) => setS({ ...s, service_impute: Number(e.target.value) })}>
            <option value="">Choisir…</option>
            {services.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}
          </select>
        </label>
        <label>Compte comptable
          <select value={s.compte ?? ''} onChange={(e) => setS({ ...s, compte: e.target.value ? Number(e.target.value) : null })}>
            <option value="">Choisir…</option>
            {comptes.map((c) => <option key={c.id} value={c.id}>{c.numero} - {c.libelle}</option>)}
          </select>
        </label>
        <label>Article NG
          <input value={compte?.article_ng ?? ''} disabled />
        </label>
        {d.est_investissement && (
          <label>Durée d'amortissement (mois)
            <input type="number" min="1" value={s.duree_amortissement ?? ''} onChange={(e) => setS({ ...s, duree_amortissement: e.target.value ? Number(e.target.value) : null })} />
          </label>
        )}
      </div>
      <label className="case">
        <input type="checkbox" checked={s.prevu_budget} onChange={(e) => setS({ ...s, prevu_budget: e.target.checked })} />
        Prévu au budget
      </label>
      {s.prevu_budget ? (
        <label>Ligne budgétaire
          <select value={s.ligne_budgetaire ?? ''} onChange={(e) => setS({ ...s, ligne_budgetaire: e.target.value ? Number(e.target.value) : null })}>
            <option value="">Choisir…</option>
            {lignes.map((l) => <option key={l.id} value={l.id}>{l.exercice} · {l.service_nom} · {l.intitule} · disponible {montant(l.disponible)}</option>)}
          </select>
        </label>
      ) : (
        <label>Motif du hors budget
          <input value={s.motif_hors_budget} onChange={(e) => setS({ ...s, motif_hors_budget: e.target.value })} />
        </label>
      )}
      {lignes.length === 0 && <p className="aide">Aucune ligne budgétaire. Elles se saisissent dans l'administration, rubrique Lignes budgétaires.</p>}
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button className="secondaire" disabled={enCours} onClick={enregistrer}>Enregistrer l'imputation</button>
      </div>
    </fieldset>
  )
}

export default function DetailBudget({ id }: { id: number }) {
  const [d, setD] = useState<DemandeBudget | null>(null)
  const [erreur, setErreur] = useState('')
  const [texte, setTexte] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    api<DemandeBudget>(`${URL}/${id}/`).then(setD).catch((e: Error) => setErreur(e.message))
  }, [id])
  useEffect(charger, [charger])

  async function agir(action: string, corps: object = {}) {
    setEnCours(true)
    setErreur('')
    try {
      setD(await api<DemandeBudget>(`${URL}/${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
      setTexte('')
    } catch (e) {
      setErreur((e as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const pdf = () => ouvrirFichier(`${URL}/${id}/pdf/`).catch((e: Error) => setErreur(e.message))

  if (!d) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const b = d.situation_budget
  const accord = d.statut === 'ATT_ACCORD'

  return (
    <div className="fiche">
      <p><a href="#/budget">← Demandes liées au budget</a></p>
      <div className="barre">
        <h2>{d.numero}</h2>
        <button className="secondaire" onClick={pdf}>Fiche PDF</button>
      </div>
      <p className="statut">
        {d.statut_libelle}
        {d.fast_track && <> <span className="pastille u1">Fast-Track</span></>}
        {!d.prevu_budget && <> <span className="pastille partielle">Hors budget</span></>}
      </p>
      <p className="aide">{d.type_libelle}</p>

      <dl>
        <dt>Intitulé</dt><dd><strong>{d.intitule}</strong></dd>
        {d.description && <><dt>Description</dt><dd>{d.description}</dd></>}
        <dt>Demandeur</dt><dd>{d.demandeur_nom}{d.demandeur_fonction && `, ${d.demandeur_fonction}`} · {d.service_nom} · {d.site_nom}</dd>
        <dt>Date</dt><dd>{dateFr(d.date)}</dd>
        {d.activite_libelle && <><dt>Activité</dt><dd>{d.activite_libelle}</dd></>}
        {d.projet_nom && <><dt>Projet / client</dt><dd>{d.projet_nom} · code analytique {d.code_analytique}</dd></>}
        {d.est_investissement && (
          <><dt>Investissement</dt><dd>{[d.nature_libelle, d.motif_investissement_libelle, d.numero_contrat && `contrat ${d.numero_contrat}`,
            d.client_nom, d.loyer_mensuel && `loyer mensuel ${montant(d.loyer_mensuel)}`].filter(Boolean).join(' · ')}</dd></>
        )}
        {d.acheteur_nom && <><dt>Acheteur</dt><dd>{d.acheteur_nom}</dd></>}
        {d.ancien_numero && <><dt>Ancien logiciel</dt><dd>{d.ancien_numero}</dd></>}
      </dl>

      {d.peut_consulter ? <Consultation d={d} onChange={setD} /> : d.devis.length > 0 && (
        <>
          <h3>Mise en concurrence</h3>
          <div className="defilant">
            <table>
              <thead><tr><th>Fournisseur</th><th>N° de devis</th><th>Date</th><th className="nombre">Montant</th><th></th></tr></thead>
              <tbody>
                {d.devis.map((x) => (
                  <tr key={x.id}>
                    <td>{x.retenu ? <strong>{x.fournisseur_nom}</strong> : x.fournisseur_nom}</td><td>{x.numero}</td><td>{dateFr(x.date)}</td>
                    <td className="nombre">{montant(x.montant)}</td><td>{x.retenu && <span className="pastille complete">Retenu</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="aide">
            Critères : {[d.critere_qualite && 'qualité', d.critere_delai && 'délai', d.critere_prix && 'prix', d.critere_autre].filter(Boolean).join(', ') || 'non précisés'}
            {d.justification_devis && ` · ${d.justification_devis}`}
          </p>
        </>
      )}

      {d.peut_imputer && <Imputation key={d.compte ?? 0} d={d} onChange={setD} />}

      <h3>Imputation et budget</h3>
      <dl>
        <dt>Montant</dt><dd>{d.montant ? <strong>{montant(d.montant)} XOF</strong> : 'après consultation'}</dd>
        <dt>Imputation</dt><dd>{d.compte_nom ? `${d.service_impute_nom} · ${d.compte_nom} · ${d.article_ng}` : 'à renseigner par le contrôle de gestion'}</dd>
        <dt>Budget</dt><dd>{d.prevu_budget ? d.ligne_budgetaire_nom || 'ligne à préciser' : `Hors budget : ${d.motif_hors_budget}`}</dd>
        {d.duree_amortissement && <><dt>Amortissement</dt><dd>{d.duree_amortissement} mois</dd></>}
      </dl>
      {b && (
        <div className="defilant">
          <table>
            <thead><tr><th className="nombre">Budget</th><th className="nombre">Déjà engagé</th><th className="nombre">Disponible</th><th className="nombre">À engager</th><th className="nombre">Solde</th></tr></thead>
            <tbody>
              <tr>
                <td className="nombre">{montant(b.budget)}</td><td className="nombre">{montant(b.engage)}</td><td className="nombre">{montant(b.disponible)}</td>
                <td className="nombre">{montant(b.a_engager)}</td>
                <td className={`nombre ${Number(b.solde) < 0 ? 'erreur' : ''}`}><strong>{montant(b.solde)}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
      {d.motifs_dg.length > 0 && <p className="aide">Validation de la direction générale requise : {d.motifs_dg.join(', ')}.</p>}

      <h3>Visas</h3>
      <ul>
        {d.signatures.map((s) => (
          <li key={s.etape}>{s.etape} : {s.auteur ? <><strong>{s.auteur}</strong> le {dateHeureFr(s.date)}</> : <span className="aide">en attente</span>}</li>
        ))}
      </ul>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      {d.modifiable && (
        <div className="actions">
          <button disabled={enCours} onClick={() => agir('soumettre')}>Soumettre pour validation</button>
          <a className="bouton secondaire" href={`#/budget/${d.id}/modifier`}>Modifier</a>
        </div>
      )}

      {(d.peut_valider || d.peut_consulter) && (
        <fieldset>
          <legend>{d.peut_valider ? 'Votre décision' : 'Renvoi au demandeur'}</legend>
          <label>Commentaire ou motif
            <textarea value={texte} onChange={(e) => setTexte(e.target.value)} />
          </label>
          <div className="actions">
            {d.peut_valider && <button disabled={enCours} onClick={() => agir('valider', { commentaire: texte })}>{accord ? "Donner l'accord" : 'Valider'}</button>}
            <button className="secondaire" disabled={enCours} onClick={() => agir('renvoyer', { commentaire: texte })}>À représenter (renvoyer au demandeur)</button>
            {d.peut_valider && <button className="danger" disabled={enCours} onClick={() => agir('refuser', { commentaire: texte })}>Refuser</button>}
          </div>
        </fieldset>
      )}

      {d.statut === 'VALIDEE' && (
        <>
          <h3>Bons de commande</h3>
          {d.bons_commande.length === 0 && <p className="aide">Aucun bon de commande pour cette demande.</p>}
          <ul>
            {d.bons_commande.map((x) => <li key={x.id}><a href={`#/commandes/${x.id}`}>{x.numero}</a> · {x.statut_libelle}</li>)}
          </ul>
          {d.peut_commander && <div className="actions"><a className="bouton" href={`#/budget/${d.id}/commander`}>Créer un bon de commande</a></div>}
        </>
      )}

      <h3>Historique</h3>
      {d.evenements.length === 0 && <p className="aide">Brouillon, pas encore soumis.</p>}
      <ul>
        {d.evenements.map((e) => (
          <li key={e.id}>
            {dateHeureFr(e.date)} · <strong>{e.action_libelle}</strong>{e.etape_libelle && ` (${e.etape_libelle.replace('En attente ', '')})`} par {e.auteur_nom}
            {e.commentaire && ` : ${e.commentaire}`}
          </li>
        ))}
      </ul>
    </div>
  )
}
