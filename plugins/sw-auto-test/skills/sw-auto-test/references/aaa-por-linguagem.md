# AAA em cada linguagem

Language examples (use the idiom of each framework):

PHP (PHPUnit / Pest):
```php
public function test_returns_error_when_email_is_invalid(): void
{
    // Arrange
    $validator = new EmailValidator();
    $invalidEmail = 'not-an-email';

    // Act
    $result = $validator->validate($invalidEmail);

    // Assert
    $this->assertFalse($result->isValid());
    $this->assertSame('invalid_format', $result->errorCode());
}
```

Python (pytest):
```python
def test_returns_error_when_email_is_invalid():
    # Arrange
    validator = EmailValidator()
    invalid_email = "not-an-email"

    # Act
    result = validator.validate(invalid_email)

    # Assert
    assert result.is_valid is False
    assert result.error_code == "invalid_format"
```

TypeScript (Vitest / Jest):
```typescript
it('returns error when email is invalid', () => {
  // Arrange
  const validator = new EmailValidator();
  const invalidEmail = 'not-an-email';

  // Act
  const result = validator.validate(invalidEmail);

  // Assert
  expect(result.isValid).toBe(false);
  expect(result.errorCode).toBe('invalid_format');
});
```

Go (testing):
```go
func TestReturnsErrorWhenEmailIsInvalid(t *testing.T) {
    // Arrange
    validator := NewEmailValidator()
    invalidEmail := "not-an-email"

    // Act
    result := validator.Validate(invalidEmail)

    // Assert
    if result.IsValid {
        t.Errorf("expected invalid, got valid")
    }
    if result.ErrorCode != "invalid_format" {
        t.Errorf("expected error_code 'invalid_format', got %q", result.ErrorCode)
    }
}
```

Java (JUnit 5):
```java
@Test
void returnsErrorWhenEmailIsInvalid() {
    // Arrange
    EmailValidator validator = new EmailValidator();
    String invalidEmail = "not-an-email";

    // Act
    ValidationResult result = validator.validate(invalidEmail);

    // Assert
    assertFalse(result.isValid());
    assertEquals("invalid_format", result.getErrorCode());
}
```

Ruby (RSpec):
```ruby
it 'returns error when email is invalid' do
  # Arrange
  validator = EmailValidator.new
  invalid_email = 'not-an-email'

  # Act
  result = validator.validate(invalid_email)

  # Assert
  expect(result.valid?).to be false
  expect(result.error_code).to eq('invalid_format')
end
```

