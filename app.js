(() => {
  const $ = (selector) => document.querySelector(selector);
  const grid = $("#listingGrid");
  const filters = { area: $("#areaFilter"), type: $("#typeFilter"), budget: $("#budgetFilter"), setup: $("#setupFilter"), furnish: $("#furnishFilter"), parking: $("#parkingFilter"), utility: $("#utilityFilter"), sort: $("#sortFilter") };
  const state = { saved: new Set(JSON.parse(localStorage.getItem("roomroute-saved") || "[]")), onlySaved: false, visible: 12 };
  let listingRecords = [];
  let ownerRecords = [];
  let previewSummary = { listings: 0, owners: 0, students: 0, employees: 0, inquiries: 0 };
  let inquiryRecords = [];
  let ownerListings = [];
  let csrfToken = null;
  let sessionUser = null;
  let pendingInquiry = null;
  async function api(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (options.method && options.method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
    const response = await fetch(path, { credentials: "same-origin", ...options, headers });
    const payload = response.status === 204 ? {} : await response.json();
    if (!response.ok) throw new Error(payload.error || "The request could not be completed.");
    return payload;
  }
  async function refreshData() {
    const [inventory, summary, auth] = await Promise.all([api("/api/listings"), api("/api/summary"), api("/api/auth/session")]);
    listingRecords = inventory.listings;
    ownerRecords = inventory.owners;
    previewSummary = summary;
    const hasSampleListings=Number(summary.sampleListings||0)>0;
    $("#inventoryNotice").textContent=hasSampleListings?"This inventory includes fictional sample listings. Each is labelled; confirm live listings with the owner.":"Listing details are supplied by owners. Confirm details and availability before paying.";
    $("#demoDisclaimer").textContent=hasSampleListings?"Includes fictional sample listings and profiles, marked in the service.":"Listing details are supplied by owners. Confirm details and availability before paying.";
    sessionUser = auth.user;
    csrfToken = auth.csrfToken;
    if (sessionUser?.role === "owner") {
      [inquiryRecords, ownerListings] = await Promise.all([api("/api/inquiries"), api("/api/owner/listings")]);
    } else { inquiryRecords = []; ownerListings = []; }
    $("#avatarButton").textContent = sessionUser?.name?.[0]?.toUpperCase() || "A";
    $("#avatarButton").setAttribute("aria-label", sessionUser ? `Account: ${sessionUser.name}` : "Sign in or create an account");
  }
  const money = (amount) => `₹${Number(amount).toLocaleString("en-IN")}`;
  const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[character]);
  const ownerFor = (listing) => ownerRecords.find((owner) => owner.id === listing.ownerId);
  const hideModal = () => { $("#modalBackdrop").hidden = true; document.body.classList.remove("modal-open"); };
  const showModal = (html) => { $("#modalContent").innerHTML = html; $("#modalBackdrop").hidden = false; document.body.classList.add("modal-open"); };
  const toast = (message) => { const el=$("#toast"); el.textContent=message; el.classList.add("show"); clearTimeout(toast.timer); toast.timer=setTimeout(()=>el.classList.remove("show"),2600); };
  const saveState = () => { localStorage.setItem("roomroute-saved",JSON.stringify([...state.saved])); $("#savedCount").textContent=state.saved.size; };

  function showAuth(preferredRole = null) {
    const chosenRole = preferredRole || "student";
    showModal(`<div class="dashboard-head"><div class="detail-eyebrow">ROOMROUTE ACCOUNT</div><h2 id="modalTitle">Welcome back</h2><p>Sign in to send inquiries or manage a listing. New here? Create an account.</p></div><div class="auth-tabs"><button type="button" class="auth-tab active" id="loginTab">Sign in</button><button type="button" class="auth-tab" id="registerTab">Create account</button></div><form class="inquiry-form auth-form" id="authForm"><div id="authNameField" hidden><label>Your name<input name="name" minlength="2" maxlength="80" autocomplete="name" placeholder="Your full name"/></label></div><label>Email<input name="email" type="email" required maxlength="254" autocomplete="email" placeholder="you@example.com"/></label><div id="authRoleField" hidden><label>I'm joining as<select name="role"><option value="${escapeHTML(chosenRole)}">${chosenRole==="owner"?"Property owner":"Student"}</option>${chosenRole==="owner"?'<option value="student">Student</option><option value="employee">Employee</option>':'<option value="employee">Employee</option><option value="owner">Property owner</option>'}</select></label></div><label>Password<input name="password" type="password" required minlength="12" maxlength="256" autocomplete="current-password" placeholder="At least 12 characters"/></label><button class="text-button" type="button" id="forgotPassword">Forgot password?</button><button class="text-button" type="button" id="resendVerification">Resend verification email</button><p class="auth-hint" id="authHint">Your account requires a verified email address.</p><button class="search-button" type="submit" id="authSubmit">Sign in <span>→</span></button><p class="auth-error" id="authError" role="alert"></p></form>`);
    let mode="login";
    const setMode=(next)=>{mode=next;const registering=mode==="register";$("#authNameField").hidden=!registering;$("#authRoleField").hidden=!registering;$("#authForm [name=password]").autocomplete=registering?"new-password":"current-password";$("#authForm [name=password]").minLength=registering?12:1;$("#authForm [name=password]").required=true;$("#authSubmit").innerHTML=`${registering?"Create account":"Sign in"} <span>→</span>`;$("#modalTitle").textContent=registering?"Create your account":"Welcome back";$("#loginTab").classList.toggle("active",!registering);$("#registerTab").classList.toggle("active",registering);$("#forgotPassword").hidden=registering;$("#resendVerification").hidden=registering;$("#authHint").textContent=registering?"We’ll email a verification link before you can sign in.":"Use a verified email address. Sample profiles have no sign-in credentials.";};
    $("#loginTab").onclick=()=>setMode("login"); $("#registerTab").onclick=()=>setMode("register");
    $("#forgotPassword").onclick=async()=>{const email=$("#authForm [name=email]").value.trim();if(!email){$("#authError").textContent="Enter your email address first.";return;}try{const result=await api("/api/auth/password-reset/request",{method:"POST",body:JSON.stringify({email})});$("#authError").textContent=result.message;}catch(error){$("#authError").textContent=error.message;}};
    $("#resendVerification").onclick=async()=>{const email=$("#authForm [name=email]").value.trim();if(!email){$("#authError").textContent="Enter your email address first.";return;}try{const result=await api("/api/auth/resend-verification",{method:"POST",body:JSON.stringify({email})});$("#authError").textContent=result.message;}catch(error){$("#authError").textContent=error.message;}};
    $("#authForm").onsubmit=async(e)=>{e.preventDefault();const form=e.currentTarget;const values=new FormData(form);const button=$("#authSubmit");button.disabled=true;button.textContent="Please wait…";$("#authError").textContent="";try{const result=await api(`/api/auth/${mode}`,{method:"POST",body:JSON.stringify({name:values.get("name"),email:values.get("email"),password:values.get("password"),role:values.get("role")||chosenRole})});if(mode==="register"){setMode("login");$("#authForm [name=email]").value=values.get("email");$("#authError").textContent=result.message;button.disabled=false;return;}sessionUser=result.user;csrfToken=result.csrfToken;await refreshData();hideModal();toast(`Signed in as ${sessionUser.name}`);if(pendingInquiry){const pending=pendingInquiry;pendingInquiry=null;openDetails(pending.listingId);$("#inquiryMessage").value=pending.message;$("#inquiryForm").requestSubmit();}else if(sessionUser.role==="owner")ownerDashboard();}catch(error){$("#authError").textContent=error.message;button.disabled=false;button.innerHTML=`${mode==="register"?"Create account":"Sign in"} <span>→</span>`;}};
    $("#authForm [name=email]").focus();
  }

  const areas = ["Dharampeth", "Bajaj Nagar", "Laxmi Nagar", "Pratap Nagar", "Manish Nagar", "Trimurti Nagar", "Ramdaspeth", "Civil Lines", "Sadar", "Wardha Road"];
  areas.forEach((area)=>filters.area.insertAdjacentHTML("beforeend",`<option value="${area}">${area}</option>`));
  saveState();

  function filteredListings() {
    let rows=listingRecords.filter((l)=>{
      if(state.onlySaved&&!state.saved.has(l.id)) return false;
      if(filters.area.value&&l.area!==filters.area.value) return false;
      if(filters.type.value&&l.type!==filters.type.value) return false;
      if(filters.budget.value&&l.rent>Number(filters.budget.value)) return false;
      if(filters.setup.value&&((filters.setup.value==="Shared")!==(l.type==="Shared room"))) return false;
      if(filters.furnish.value&&l.furnishing!==filters.furnish.value) return false;
      if(filters.parking.value==="yes"&&!l.parking) return false;
      if(filters.utility.value==="included"&&!l.electricityIncluded) return false;
      if(filters.utility.value==="separate"&&l.electricityIncluded) return false;
      return true;
    });
    if(filters.sort.value==="rent-low") rows.sort((a,b)=>a.rent-b.rent);
    if(filters.sort.value==="rent-high") rows.sort((a,b)=>b.rent-a.rent);
    if(filters.sort.value==="newest") rows.sort((a,b)=>a.updatedDays-b.updatedDays);
    return rows;
  }
  function render() {
    const rows=filteredListings();
    const active=[filters.area,filters.type,filters.budget,filters.setup,filters.furnish,filters.parking,filters.utility].filter((f)=>f.value).length;
    $("#filterBadge").hidden=!active; $("#filterBadge").textContent=active;
    $("#resultCount").textContent=rows.length;
    $("#resultsTitle").firstChild.textContent=state.onlySaved?"Your saved places ":"Places to call home ";
    $("#activeFilters").innerHTML=[filters.area,filters.type,filters.budget,filters.setup,filters.furnish,filters.parking,filters.utility].filter((f)=>f.value).map((f)=>`<button class="filter-chip" data-clear="${f.id}">${f.selectedOptions[0].textContent} <span>×</span></button>`).join("");
    $("#activeFilters").querySelectorAll("[data-clear]").forEach((b)=>b.onclick=()=>{document.getElementById(b.dataset.clear).value="";render();});
    grid.innerHTML=rows.slice(0,state.visible).map((l)=>`<article class="listing-card"><button class="photo-button" data-detail="${escapeHTML(l.id)}" aria-label="View ${escapeHTML(l.title)}"><img loading="lazy" src="${escapeHTML(l.photo)}" alt="Interior of ${escapeHTML(l.type.toLowerCase())} in ${escapeHTML(l.area)}"/><span class="photo-tag">${l.isSample?"Sample · ":""}${escapeHTML(l.type)}</span></button><button class="heart-button ${state.saved.has(l.id)?"is-saved":""}" data-save="${escapeHTML(l.id)}" aria-label="${state.saved.has(l.id)?"Remove from":"Save to"} shortlist">${state.saved.has(l.id)?"♥":"♡"}</button><button class="card-content" data-detail="${escapeHTML(l.id)}"><div class="card-title-row"><h3>${escapeHTML(l.title)}</h3></div><p class="card-location">⌖ ${escapeHTML(l.area)}, Nagpur <span>·</span> ${escapeHTML(l.furnishing)}</p><div class="feature-chips"><span>${l.type.includes("flat")?`${l.beds} bed · ${l.baths} bath`:escapeHTML(l.type)}</span><span>${l.parking?"Parking":"No parking"}</span></div><div class="card-cost"><strong>${money(l.rent)}<small> / month</small></strong><span>${l.electricityIncluded?"Electricity included":"Electricity separate"}</span></div><div class="availability">Available ${escapeHTML(l.availableFrom)}</div></button></article>`).join("");
    grid.querySelectorAll("[data-save]").forEach((b)=>b.onclick=(e)=>{e.stopPropagation();const id=b.dataset.save;state.saved.has(id)?state.saved.delete(id):state.saved.add(id);saveState();render();toast(state.saved.has(id)?"Added to your shortlist":"Removed from shortlist");});
    grid.querySelectorAll("[data-detail]").forEach((b)=>b.onclick=()=>openDetails(b.dataset.detail));
    $("#emptyState").hidden=rows.length!==0; $("#loadMore").hidden=rows.length<=state.visible;
  }
  function openDetails(id) {
    const l=listingRecords.find((x)=>x.id===id), owner=ownerFor(l);
    showModal(`<div class="detail-gallery"><img src="${escapeHTML(l.gallery[0])}" alt="Room or flat interior"/><img src="${escapeHTML(l.gallery[1])}" alt="Additional view of the property"/></div><div class="detail-body"><div class="detail-eyebrow">${escapeHTML(l.type.toUpperCase())} <span>·</span> ${escapeHTML(l.area.toUpperCase())}, NAGPUR</div><h2 id="modalTitle">${escapeHTML(l.title)}</h2><p class="detail-summary">${escapeHTML(l.summary)}</p><div class="detail-price">${money(l.rent)} <small>/ month</small><span>Deposit ${money(l.deposit)}</span></div><div class="detail-facts"><div><small>FURNISHING</small><b>${escapeHTML(l.furnishing)}</b></div><div><small>ELECTRICITY</small><b>${l.electricityIncluded?"Included":"Separate bill"}</b></div><div><small>PARKING</small><b>${l.parking?"Available":"Not available"}</b></div><div><small>AVAILABLE FROM</small><b>${new Date(l.availableFrom).toLocaleDateString("en-IN",{day:"numeric",month:"short"})}</b></div></div><h3 class="amenity-heading">What’s included</h3><div class="amenity-list">${l.amenities.map((a)=>`<span>✓ ${escapeHTML(a)}</span>`).join("")}</div><div class="owner-card"><span class="owner-avatar">${escapeHTML(owner.name[0])}</span><div><b>${escapeHTML(owner.name)}</b><small>${l.isSample?"Fictional sample owner":"Listing contact"}</small></div></div><p class="location-note">⌖ ${escapeHTML(l.address)} <span>Approximate neighborhood only. Confirm the exact address before visiting.</span></p>${l.isSample?'<p class="demo-note">Fictional sample listing. It has no real owner and cannot receive inquiries.</p>':`<form class="inquiry-form" id="inquiryForm"><label for="inquiryMessage">Ask about this place</label><textarea id="inquiryMessage" required minlength="8" placeholder="Hi, is this place available for a visit this week?"></textarea><button type="submit" class="search-button">Send inquiry <span>→</span></button></form><button type="button" class="text-button" id="reportListing">Report this listing</button><p class="demo-note">Your inquiry is sent to the owner’s RoomRoute inbox and email.</p>`}</div>`);
    if(!l.isSample) $("#reportListing").onclick=()=>reportListing(l.id);
    if(!l.isSample) $("#inquiryForm").onsubmit=async(e)=>{e.preventDefault();const message=$("#inquiryMessage").value;if(!sessionUser){pendingInquiry={listingId:l.id,message};showAuth("student");return;}const button=e.currentTarget.querySelector("button[type=submit]");button.disabled=true;button.textContent="Sending…";try{const saved=await api("/api/inquiries",{method:"POST",body:JSON.stringify({listingId:l.id,message})});await refreshData();hideModal();toast(saved.message);}catch(error){button.disabled=false;button.innerHTML="Send inquiry <span>→</span>";toast(error.message);}};
  }

  function reportListing(listingId) {
    if (!sessionUser) { showAuth("student"); return; }
    showModal(`<div class="dashboard-head"><div class="detail-eyebrow">SAFETY REPORT</div><h2 id="modalTitle">Report this listing</h2><p>Reports go to the RoomRoute moderation team.</p></div><form class="inquiry-form" id="reportForm"><label>Reason<select name="reason"><option>Misleading information</option><option>Already rented</option><option>Unsafe or discriminatory</option><option>Suspected scam</option><option>Other</option></select></label><label>Details (optional)<textarea name="details" maxlength="1000"></textarea></label><button class="search-button">Send report</button><p class="auth-error" id="reportError" role="alert"></p></form>`);
    $("#reportForm").onsubmit=async(event)=>{event.preventDefault();const form=event.currentTarget;const values=new FormData(form);try{const result=await api(`/api/listings/${encodeURIComponent(listingId)}/report`,{method:"POST",body:JSON.stringify({reason:values.get("reason"),details:values.get("details")})});hideModal();toast(result.message);}catch(error){$("#reportError").textContent=error.message;}};
  }
  function ownerDashboard() {
    if(!sessionUser){showAuth("owner");return;}
    if(sessionUser.role!=="owner"){toast("Sign in with an owner account to manage a place.");return;}
    const ownedListings=ownerListings;
    const rows=ownedListings.slice(0,8).map((l)=>`<tr><td><b>${escapeHTML(l.title)}</b><small>${escapeHTML(l.area)} · ${escapeHTML(l.type)}</small></td><td>${money(l.rent)}</td><td><span class="status-dot">●</span> ${escapeHTML(l.status)}</td><td>${l.is_sample?"Sample record":"Owner listing"}</td></tr>`).join("")||`<tr><td colspan="4">No places listed yet. Add your first place to submit it for review.</td></tr>`;
    const inbox=inquiryRecords.length?inquiryRecords.slice(0,5).map((item)=>{const timestamp=String(item.created_at||"");const normalized=timestamp.endsWith("Z")||/[+-]\d{2}:\d{2}$/.test(timestamp)?timestamp:`${timestamp}Z`;return `<div class="inbox-item"><span class="owner-avatar">${escapeHTML(item.student_name[0])}</span><div><b>${escapeHTML(item.student_name)} · ${escapeHTML(item.listing_title)}</b><p>${escapeHTML(item.message)}</p><small>${new Date(normalized).toLocaleString("en-IN")}</small></div><span class="inbox-status">${escapeHTML(item.status)}</span></div>`;}).join(""):`<div class="inbox-empty">New inquiries about your listings will appear here.</div>`;
    showModal(`<div class="dashboard-head"><div class="detail-eyebrow">OWNER WORKSPACE</div><h2 id="modalTitle">Owner overview</h2><p>Welcome, ${escapeHTML(sessionUser.name)}. Manage your places and renter inquiries.</p></div><div class="owner-stats"><div><small>YOUR PLACES</small><b>${ownedListings.length}</b><span>${ownedListings.filter((l)=>l.status==="active").length} live · others in review</span></div><div><small>INQUIRIES</small><b>${inquiryRecords.length}</b><span>Private owner inbox</span></div><div><small>MODERATION</small><b>${ownedListings.filter((l)=>l.status==="pending").length}</b><span>Awaiting review</span></div></div><div class="table-heading"><h3>Your places</h3><button class="text-button" id="newListing">＋ Add a place</button></div><div class="listing-table-wrap"><table><thead><tr><th>PLACE</th><th>MONTHLY RENT</th><th>STATUS</th><th>RECORD TYPE</th></tr></thead><tbody>${rows}</tbody></table></div><div class="table-heading"><h3>Recent inquiries</h3><span class="sample-caption">Owner notifications are sent by email</span></div><div class="inbox-list">${inbox}</div><p class="demo-note">Listings stay private until approved by a RoomRoute moderator. Inquiries are delivered to your account inbox and email.</p>`);
    $("#newListing").onclick=()=>showModal(`<div class="dashboard-head"><div class="detail-eyebrow">OWNER LISTING</div><h2 id="modalTitle">Add a place</h2><p>Enter the essentials and submit the listing for moderation.</p></div><form class="inquiry-form" id="newListingForm"><label>Listing title<input name="title" required maxlength="100" placeholder="e.g. Bright room near campus"/></label><div class="form-columns"><label>Property type<select name="type"><option>Private room</option><option>Shared room</option><option>1 BHK flat</option><option>2 BHK flat</option></select></label><label>Area<select name="area">${areas.map((a)=>`<option>${a}</option>`).join("")}</select></label></div><div class="form-columns"><label>Monthly rent (₹)<input name="rent" required type="number" min="1" max="1000000" placeholder="10000"/></label><label>Deposit (₹)<input name="deposit" required type="number" min="0" max="10000000" placeholder="20000"/></label></div><div class="form-columns"><label>Furnishing<select name="furnishing"><option>Fully furnished</option><option selected>Semi furnished</option><option>Unfurnished</option></select></label><label>Available from<input name="availableFrom" type="date" value="2026-11-01"/></label></div><div class="form-columns"><label><span>Parking</span><select name="parking"><option value="false">No parking</option><option value="true">Parking available</option></select></label><label><span>Electricity</span><select name="electricityIncluded"><option value="false">Separate bill</option><option value="true">Included in rent</option></select></label></div><label>About the place<textarea name="summary" maxlength="500" placeholder="Describe the room, utilities, and house rules"></textarea></label><button class="search-button" type="submit">Submit for review <span>→</span></button></form><p class="demo-note">Only approved listings appear publicly. Add genuine photos and accurate property details before launch.</p>`);
  }
  async function submitNewListing(event){
    event.preventDefault();const form=event.target;const f=new FormData(form);const button=form.querySelector("button[type=submit]");button.disabled=true;button.textContent="Saving…";
    try{await api("/api/listings",{method:"POST",body:JSON.stringify({title:f.get("title"),type:f.get("type"),area:f.get("area"),rent:Number(f.get("rent")),deposit:Number(f.get("deposit")),furnishing:f.get("furnishing"),availableFrom:f.get("availableFrom")||"2026-11-01",parking:f.get("parking")==="true",electricityIncluded:f.get("electricityIncluded")==="true",summary:f.get("summary")})});await refreshData();ownerDashboard();toast("Submitted for review. You’ll see the moderation status in your owner workspace.");}
    catch(error){button.disabled=false;button.innerHTML="Submit for review <span>→</span>";toast(error.message);}
  }
  function accountMenu() {
    if(!sessionUser){showAuth();return;}
    if(sessionUser.role==="moderator"){moderatorDashboard();return;}
    showModal(`<div class="dashboard-head"><div class="detail-eyebrow">SIGNED IN · ${sessionUser.isVerified?"VERIFIED":"UNVERIFIED"}</div><h2 id="modalTitle">Your account</h2><p>${escapeHTML(sessionUser.name)}<br/>${escapeHTML(sessionUser.email)}<br/>${escapeHTML(sessionUser.role)}</p></div><div class="account-actions"><button class="text-button" id="exportAccount">Download my account data</button><button class="text-button" id="deleteAccount">Delete my account</button><button class="signout-button" id="signOutButton">Sign out</button></div>`);
    $("#exportAccount").onclick=async()=>{try{const data=await api("/api/account/export");const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="roomroute-account-export.json";a.click();URL.revokeObjectURL(url);}catch(error){toast(error.message);}};
    $("#deleteAccount").onclick=()=>confirmAccountDeletion();
    $("#signOutButton").onclick=async()=>{try{await api("/api/auth/logout",{method:"POST",body:"{}"});sessionUser=null;csrfToken=null;inquiryRecords=[];hideModal();await refreshData();toast("Signed out");}catch(error){toast(error.message);}};
  }
  function confirmAccountDeletion() {
    showModal(`<div class="dashboard-head"><div class="detail-eyebrow">ACCOUNT PRIVACY</div><h2 id="modalTitle">Delete your account?</h2><p>This permanently deletes your account, owner listings, and associated inquiries. This cannot be undone.</p></div><form class="inquiry-form" id="deleteAccountForm"><label>Current password<input name="password" type="password" required autocomplete="current-password"/></label><label>Type DELETE to confirm<input name="confirmation" required autocomplete="off"/></label><button class="search-button">Permanently delete account</button><p class="auth-error" id="deleteError" role="alert"></p></form>`);
    $("#deleteAccountForm").onsubmit=async(event)=>{event.preventDefault();const form=new FormData(event.currentTarget);if(form.get("confirmation")!=="DELETE"){$("#deleteError").textContent="Type DELETE exactly to confirm.";return;}try{await api("/api/account/delete",{method:"POST",body:JSON.stringify({password:form.get("password")})});sessionUser=null;csrfToken=null;hideModal();await refreshData();toast("Your account data was deleted.");}catch(error){$("#deleteError").textContent=error.message;}};
  }
  async function moderatorDashboard() {
    try {
      const [listings,reports]=await Promise.all([api("/api/moderation/listings"),api("/api/moderation/reports")]);
      const listingRows=listings.map((l)=>`<article class="inbox-item"><div><b>${escapeHTML(l.title)}</b><p>${escapeHTML(l.owner_name)} · ${escapeHTML(l.owner_email)} · ${escapeHTML(l.area)} · ${money(l.rent)}</p><small>${escapeHTML(l.summary||"")}</small><div><button class="text-button" data-listing-action="approve" data-id="${escapeHTML(l.id)}">Approve</button><button class="text-button" data-listing-action="reject" data-id="${escapeHTML(l.id)}">Reject</button></div></div><span>${escapeHTML(l.status)}</span></article>`).join("")||"<p>No listings need review.</p>";
      const reportRows=reports.map((r)=>`<article class="inbox-item"><div><b>${escapeHTML(r.reason)} · ${escapeHTML(r.listing_title)}</b><p>${escapeHTML(r.details||"")}</p><small>Reported by ${escapeHTML(r.reporter_email)}</small><div><button class="text-button" data-report-action="reviewed" data-id="${r.id}">Mark reviewed</button><button class="text-button" data-report-action="dismissed" data-id="${r.id}">Dismiss</button></div></div></article>`).join("")||"<p>No open reports.</p>";
      showModal(`<div class="dashboard-head"><div class="detail-eyebrow">MODERATION</div><h2 id="modalTitle">Review queue</h2><p>Approve accurate listings and investigate user reports.</p></div><h3>Listings (${listings.length})</h3><div class="inbox-list">${listingRows}</div><h3>Reports (${reports.length})</h3><div class="inbox-list">${reportRows}</div><button class="signout-button" id="signOutButton">Sign out</button>`);
      document.querySelectorAll("[data-listing-action]").forEach((button)=>button.onclick=async()=>{const note=prompt("Optional moderation note:")||"";try{await api(`/api/moderation/listings/${encodeURIComponent(button.dataset.id)}`,{method:"POST",body:JSON.stringify({action:button.dataset.listingAction,note})});moderatorDashboard();}catch(error){toast(error.message);}});
      document.querySelectorAll("[data-report-action]").forEach((button)=>button.onclick=async()=>{try{await api(`/api/moderation/reports/${encodeURIComponent(button.dataset.id)}`,{method:"POST",body:JSON.stringify({status:button.dataset.reportAction})});moderatorDashboard();}catch(error){toast(error.message);}});
      $("#signOutButton").onclick=async()=>{try{await api("/api/auth/logout",{method:"POST",body:"{}"});sessionUser=null;csrfToken=null;hideModal();await refreshData();}catch(error){toast(error.message);}};
    } catch(error) { showModal(`<div class="dashboard-head"><div class="detail-eyebrow">MODERATION</div><h2 id="modalTitle">Unable to load review queue</h2><p>${escapeHTML(error.message)}</p></div>`); }
  }
  function handleAuthLink() {
    const url=new URL(window.location.href);
    const verify=url.searchParams.get("verify");
    const reset=url.searchParams.get("reset");
    if(verify){api("/api/auth/verify",{method:"POST",body:JSON.stringify({token:verify})}).then((result)=>{url.searchParams.delete("verify");history.replaceState({},"",url);toast(result.message);showAuth();}).catch((error)=>toast(error.message));}
    if(reset){
      showModal(`<div class="dashboard-head"><div class="detail-eyebrow">ACCOUNT RECOVERY</div><h2 id="modalTitle">Choose a new password</h2></div><form class="inquiry-form" id="resetForm"><label>New password<input name="password" type="password" required minlength="12" maxlength="256" autocomplete="new-password"/></label><button class="search-button">Update password</button><p id="resetError" class="auth-error" role="alert"></p></form>`);
      $("#resetForm").onsubmit=async(event)=>{event.preventDefault();try{const form=new FormData(event.currentTarget);const result=await api("/api/auth/password-reset/complete",{method:"POST",body:JSON.stringify({token:reset,password:form.get("password")})});url.searchParams.delete("reset");history.replaceState({},"",url);hideModal();toast(result.message);showAuth();}catch(error){$("#resetError").textContent=error.message;}};
    }
  }
  function clearAll() { Object.values(filters).forEach((f)=>{if(f.tagName==="SELECT") f.value="";}); filters.sort.value="recommended"; state.onlySaved=false; state.visible=12; render(); }
  Object.values(filters).forEach((f)=>f.addEventListener("change",()=>{state.onlySaved=false;state.visible=12;render();}));
  $("#searchButton").onclick=()=>$("#listingSection").scrollIntoView({behavior:"smooth"});
  $("#filterToggle").onclick=()=>{$("#filterDrawer").hidden=!$("#filterDrawer").hidden;};
  $("#clearFilters").onclick=clearAll; $("#emptyClear").onclick=clearAll;
  $("#loadMore").onclick=()=>{state.visible+=12;render();};
  $("#savedToggle").onclick=()=>{state.onlySaved=!state.onlySaved;state.visible=50;render();$("#listingSection").scrollIntoView({behavior:"smooth"});};
  $("#ownerMode").onclick=ownerDashboard; $("#ownerCta").onclick=ownerDashboard; $("#avatarButton").onclick=accountMenu;
  $("#modalClose").onclick=hideModal; $("#modalBackdrop").onclick=(e)=>{if(e.target===$("#modalBackdrop"))hideModal();};
  $("#modalContent").addEventListener("submit",(event)=>{if(event.target.id==="newListingForm")submitNewListing(event);});
  document.addEventListener("keydown",(e)=>{if(e.key==="Escape")hideModal();});
  $("#mobileMenu").onclick=()=>{$(".top-actions").classList.toggle("mobile-open");};
  grid.innerHTML = `<div class="loading-state">Finding places in Nagpur<span> · </span>loading inventory…</div>`;
  handleAuthLink();
  refreshData().then(()=>render()).catch((error)=>{
    grid.innerHTML=`<div class="server-error"><h3>RoomRoute couldn’t connect to its service</h3><p>${error.message}</p><p>Start the local app with <code>python server.py</code> or Docker Compose, then refresh this page.</p></div>`;
    $("#resultCount").textContent="—"; $("#loadMore").hidden=true;
  });
})();

