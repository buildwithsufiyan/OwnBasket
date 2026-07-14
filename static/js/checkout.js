(function(){
  'use strict';
  var form=document.getElementById('checkout-form');
  if(!form)return;
  var button=document.getElementById('place-order');
  var messages={valueMissing:'This field is required.',typeMismatch:'Enter a valid email address.',tooShort:'Please enter a little more detail.'};
  function validate(field){
    var error=document.getElementById(field.getAttribute('aria-describedby')||'');
    if(!error&&field.getAttribute('aria-describedby')){
      field.getAttribute('aria-describedby').split(' ').some(function(id){var el=document.getElementById(id);if(el&&el.classList.contains('field-error')){error=el;return true;}return false;});
    }
    var message='';
    if(!field.validity.valid){Object.keys(messages).some(function(key){if(field.validity[key]){message=messages[key];return true;}return false;});}
    field.setAttribute('aria-invalid',message?'true':'false');
    if(error)error.textContent=message;
    return !message;
  }
  form.querySelectorAll('input[required],textarea[required]').forEach(function(field){field.addEventListener('blur',function(){validate(field);});field.addEventListener('input',function(){if(field.getAttribute('aria-invalid')==='true')validate(field);});});
  form.addEventListener('submit',function(event){
    var valid=true;
    form.querySelectorAll('input[required],textarea[required]').forEach(function(field){if(!validate(field))valid=false;});
    if(!valid){event.preventDefault();var invalid=form.querySelector('[aria-invalid="true"]');if(invalid)invalid.focus();return;}
    if(button.disabled){event.preventDefault();return;}
    button.disabled=true;button.classList.add('is-loading');button.querySelector('span').textContent='Placing order…';
  });
}());
