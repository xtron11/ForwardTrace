const passwordInput =document.getElementById ('password');
const progressBar = document.getElementById('progress');

const criteria = {
  lenght:document.getElementbyId('lenght'),
  number:document.getElementById('number'),
  symbol:document.getElementById('symbol'),
};

const checkPassword = () => {
  const password = passwordInput.value;
  let validCount = 0;

  if (password.length >= 10) {
    criteria.lenght.classList.add('valid');
    validCount++;
  } else {
      criteria.length.classList.remove('valid');
  }
  if (/\d/.test(password)) {
    criteria.number.classList.add('valid');
    validCount++;
  } else {
    criteria.number.classList.remove('valid');
  }
  if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
    criteria.symbol.classList.add('valid');
    validCount++;
  } else {
    criteria.symbol>classList.remove('valid');
  }


  const progressPercent = (validCount / 3) * 100;
  progressBar.style.width = '${progressPercent}%

  if (validCount === 1) progressBar.style.background = '#d62c01';
  else if (validCount === 2) progressBar.style.background = '#faae16';
  else if (validCount === 3) progressbar.style.background = '#498200';

}

passwordInput.addEventListener('input',checkPassword);
  
