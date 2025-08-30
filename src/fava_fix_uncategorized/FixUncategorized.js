// @ts-check
function markTxnModified(txnBlock) {
  txnBlock.dataset.modified = "true";
  txnBlock.classList.add("txn-modified");
}

function createPostingRow(account = "", amount = "") {
  const template = document.getElementById("posting-row-template");
  const row = template.content.cloneNode(true);

  const tr = row.querySelector("tr");
  const accountInput = tr.querySelector(".account-col input");
  const amountInput = tr.querySelector(".amount-col input");

  // Set initial values if provided
  accountInput.value = account;
  amountInput.value = amount;

  accountInput.addEventListener("input", (e) => {
    markTxnModified(e.target.closest(".txn-block"));
  });
  amountInput.addEventListener("input", (e) => {
    markTxnModified(e.target.closest(".txn-block"));
  });
  
  // Handle Enter key to trigger save
  const handleEnterKey = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      saveAllTransactions();
    }
  };
  accountInput.addEventListener("keydown", handleEnterKey);
  amountInput.addEventListener("keydown", handleEnterKey);

  // Awesomplete from UL list
  new Awesomplete(tr.querySelector(".account-select"), {
    list: "#expense-accounts-list",
    minChars: 1,
    maxItems: 20
  });

  // Action buttons
  tr.querySelector(".delete-btn").onclick = (e) => {
    markTxnModified(e.target.closest(".txn-block"));
    tr.remove();
  };

  tr.querySelector(".add-below-btn").onclick = (e) => {
    markTxnModified(e.target.closest(".txn-block"));
    const newRow = createPostingRow();
    tr.parentNode.insertBefore(newRow, tr.nextSibling);
  };

  tr.querySelector(".move-up-btn").onclick = (e) => {
    markTxnModified(e.target.closest(".txn-block"));
    const prev = tr.previousElementSibling;
    if (prev) tr.parentNode.insertBefore(tr, prev);
  };

  tr.querySelector(".move-down-btn").onclick = (e) => {
    markTxnModified(e.target.closest(".txn-block"));
    const next = tr.nextElementSibling;
    if (next && next !== tr) {
      tr.parentNode.insertBefore(next, tr);
    }
  };

  return tr;
}

function setupEditableNarration(block, narration) {
  const narrationElement = block.querySelector(".txn-narration");
  narrationElement.textContent = `${narration || "(no narration)"}`;

  let originalValue = narration;
  let isEditing = false;
  narrationElement.addEventListener('click', () => {
    if (isEditing) return;
    
    isEditing = true;
    narrationElement.classList.add('editing');
    
    // Create input field
    const input = document.createElement('input');
    input.type = 'text';
    input.value = originalValue;
    input.placeholder = 'Enter narration';
    
    // Replace content with input
    narrationElement.innerHTML = '';
    narrationElement.appendChild(input);
    input.focus();
    input.select();
    
    // Handle save/cancel
    const finishEditing = (save = false) => {
      if (!isEditing) return;
      
      isEditing = false;
      narrationElement.classList.remove('editing');
      
      if (save && input.value !== originalValue) {        
        // Mark transaction as modified
        const txnBlock = narrationElement.closest('.txn-block');
        markTxnModified(txnBlock);
        
        // Store the new narration value as data attribute
        txnBlock.dataset.narration = input.value;
      }
      narrationElement.textContent = `${input.value || "(no narration)"}`;
    };
    
    // Save on Enter, cancel on Escape
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        finishEditing(true);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        finishEditing(false);
      }
    });
    
    // Save on blur
    input.addEventListener('blur', () => finishEditing(true));
  });
}

function renderTransaction(txn, index) {
  const txnList = document.getElementById("txn-list");
  const txnTemplate = document.getElementById("txn-template");
  const rowTemplate = document.getElementById("posting-row-template");

  const el = txnTemplate.content.cloneNode(true);
  const block = el.querySelector(".txn-block");
  block.id = `split-container-${index}`;
  block.dataset.lineno = txn.lineno;
  block.dataset.hash = txn.hash;
  
  // Add txn-unclassified class if needed
  if (txn.unclassified) {
    block.classList.add('txn-unclassified');
  }

  // Set the transaction title
  const title = `${txn.date} - ${txn.payee}`;
  block.querySelector(".txn-title").textContent = title;
  block.querySelector(".txn-lineno").textContent = txn.lineno;  
  setupEditableNarration(block, txn.narration);

  // Show original postings
  const tbody = block.querySelector(".txn-splits-body");
  const postingContainer = block.querySelector(".txn-postings");
  var hasEditableExpenses = false;
  txn.postings.forEach(post => {
    if (post.editable) {
      hasEditableExpenses = true;
      tbody.appendChild(createPostingRow(post.account, post.amount));
    } else {
      const lineSpan = document.createElement("div");
      const line = document.createElement("code");
      lineSpan.appendChild(line);
      line.textContent = `  ${post.account}  ${post.amount}`;
      postingContainer.appendChild(lineSpan);
    }
  });
  // Add first editable row
  if (!hasEditableExpenses) {
    tbody.appendChild(createPostingRow(null, null));
    block.classList.add("empty-txn");
  }
  if (txn.errors) {
    block.querySelector(".txn-error-message").textContent = txn.errors;
    block.classList.add("error");
  }

  txnList.appendChild(el);
}

function serializeSplitInputs(container) {
  const splits = [];
  const rows = container.querySelectorAll("tbody tr");
  for (const row of rows) {
    const accountInput = row.querySelector(".expense-account-input");
    const amountInput = row.querySelector(".expense-amount");
    const account = accountInput?.value?.trim();
    const amount = amountInput?.value?.trim();
    if (account) {
      splits.push({ account, amount });
    }
  }
  return splits;
}

let isSaving = false;

function gatherModifiedTransactions() {
  const txnBlocks = document.querySelectorAll(".txn-block");
  const modifiedTxns = [];

  txnBlocks.forEach((block) => {
    const table = block.querySelector(".txn-splits-table");
    if (block.dataset.modified !== "true") return;

    const lineno = parseInt(block.dataset.lineno, 10);
    const hash = block.dataset.hash;
    const postings = serializeSplitInputs(block);
    
    // Always include current narration (from data attribute or original)
    const narration = block.dataset.narration;

    modifiedTxns.push({ lineno, hash, postings, narration });
  });

  return modifiedTxns;
}

async function saveAllTransactions() {
  if (isSaving) return; // Prevent double submit
  isSaving = true;

  const container = document.getElementById("txn-list");
  const saveButton = document.getElementById("save-all-btn");

  container.classList.add("saving");
  saveButton.disabled = true;

  const modifiedTxns = gatherModifiedTransactions();
  if (modifiedTxns.length === 0) {
    alert("No modified transactions to save.");
    
    container.classList.remove("saving");
    saveButton.disabled = false;
    isSaving = false;
    return;
  }

  try {
    const res = await fetch("save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transactions: modifiedTxns }),
    });

    if (!res.ok) {
      throw new Error("Failed to save transactions.");
    }

    const result = await res.json();
    if (!result.success) {
      throw new Error("Error while saving transactions: ", result.error);
    }

    // Re-fetch the full transaction list
    loadTransactions();
    saveButton.disabled = false;
    isSaving = false;
  } catch (err) {
    console.error("Error saving transactions:", err);
    alert("An error occurred while saving transactions.");

    container.classList.remove("saving");
    saveButton.disabled = false;
    isSaving = false;
  }
}


// Filtering logic
function filterTransactions() {
  const onlyUncategorized = document.getElementById('only-uncategorized').checked;
  document.querySelectorAll('.txn-block').forEach(block => {
    if (onlyUncategorized) {
      block.style.display = block.classList.contains('txn-unclassified') ? '' : 'none';
    } else {
      block.style.display = '';
    }
  });
}

function loadTransactions() {
  const params = window.location.search;
  // Load transactions on page load
  fetch("list" + params)
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        const container = document.getElementById("txn-list")          
        container.innerHTML = "";
        container.classList.remove("saving");
        data.transactions.forEach((txn, idx) => renderTransaction(txn, idx));
        filterTransactions();
      } else {
        document.getElementById("txn-list").innerHTML = "<p>Error loading transactions.</p>";
      }
    });
}

function ensureAwesompleteLoaded() {
  if (typeof Awesomplete !== "undefined") return Promise.resolve();

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/awesomplete/1.1.5/awesomplete.min.js";   // adjust path
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

/** @type import("../../../../frontend/src/extensions").ExtensionModule */
export default {
  init() {
    console.log("initialising extension");
  },
  onPageLoad() {
    console.log("a Fava report page has loaded", window.location.pathname);
  },
  async onExtensionPageLoad(ctx) {
    console.log(
      "the page for the PortfolioList extension has loaded",
      window.location.pathname,
    );

    await ensureAwesompleteLoaded();
    loadTransactions();
  
    document.getElementById('only-uncategorized').addEventListener('change', filterTransactions);
  
    document.getElementById("save-all-btn").onclick = () => {
      console.log("saving");
      saveAllTransactions();
    };
  },
};